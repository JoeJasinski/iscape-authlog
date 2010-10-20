import logging
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse, NoReverseMatch
from authlog  import models 
import authlog

if authlog.AUTHLOG_LOG_TO_FILE:
    log = logging.getLogger(authlog.AUTHLOG_LOGGER)
    log.info('AUTHLOG: BEGIN LOG')
    log.info('Using version ' + authlog.get_version())   
 

def hide_passwd(key, value):
    if key == 'password':
        return key, '*********'
    else:
        return key, value

def query2str(items):
    return '\n'.join(['%s=%s' % (hide_passwd(k, v)) for k,v in items ])

def get_tracked_models():
    return [ tuple([ i.lower() for i in j.split('.') ]) for j in authlog.AUTHLOG_TRACKED_MODELS ]
       

def watch_login(func):
    """
    Used to decorate the django.contrib.admin.site.login method.
    """

    def decorated_login(request, *args, **kwargs):
        response = func(request, *args, **kwargs)

        if func.__name__ == 'decorated_login':
            # if we're dealing with this function itself, don't bother checking
            # for invalid login attempts.  I suppose there's a bunch of
            # recursion going on here that used to cause one failed login
            # attempt to generate 10+ failed access attempt records (with 3
            # failed attempts each supposedly)
            return response

        if request.method == 'POST':
            # see if the login was successful
            login_unsuccessful = (
                response and
                not response.has_header('location') and
                response.status_code != 302
            )
            if check_request(request, login_unsuccessful):
                return response

        return response

    return decorated_login


def watch_view(func):

    def decorated_view(request_func, *args, **kwargs):
        response = func(request_func, *args, **kwargs)
    
        if func.__name__ == 'decorated_view':
            return response

        try:
            request = args[0]
        except: 
            request = None   # should never get here
            user, ip, path, accept, ua, get, post = ('None','', '<unknown>', '<unknown>', '<unknown>', '','') 
            current_path = '/'
        else:
            current_path = request.path_info
            user = request.user
            ip = request.META.get('REMOTE_ADDR', '')[:255]
            path = request.META.get('PATH_INFO', '<unknown>')[:255]
            accept = request.META.get('HTTP_ACCEPT', '<unknown>')[:255]
            ua = request.META.get('HTTP_USER_AGENT', '<unknown>')[:255]
            get = query2str(request.GET.items())
            post = query2str(request.POST.items())

        tracked_models = get_tracked_models() 
        tracked_urls = []
        for tmodel in tracked_models:
            try:
                app = tmodel[0]
                model = tmodel[1]
            except IndexError:
                pass # should only get here if someone does not specify correct tracked models
            else:
                try:
                    first_arg = args[1]
                except IndexError:
                    first_arg = None

                try:
                    if first_arg:
                        tracked_urls = tracked_urls + [
                          reverse('admin:%s_%s_change' % (app, model), args=(first_arg,)),
                          reverse('admin:%s_%s_delete' % (app, model), args=(first_arg,)),
                          reverse('admin:%s_%s_history' % (app, model), args=(first_arg,)),
                        ]
                    else:
                        tracked_urls = tracked_urls + [
                          reverse('admin:%s_%s_changelist' % (app, model),),
                          reverse('admin:%s_%s_add' % (app, model),),
                        ]

                except NoReverseMatch:
                    pass  # should only get here if tracked_models is wrong (no view associated)

        if current_path in tracked_urls:
            models.AccessPage.objects.create(
               user = user, user_agent = ua, ip_address = ip,
               get_data = get, post_data = post, http_accept = accept, 
               path_info = path, 
            ) 
       	
	return response

    return decorated_view


def check_request(request, login_unsuccessful):
    ip = request.META.get('REMOTE_ADDR', '')[:255]
    path = request.META.get('PATH_INFO', '<unknown>')[:255]
    accept = request.META.get('HTTP_ACCEPT', '<unknown>')[:255]
    ua = request.META.get('HTTP_USER_AGENT', '<unknown>')[:255]
    time = datetime.now()
    get = query2str(request.GET.items())
    post = query2str(request.POST.items())
    
    if login_unsuccessful:
        login_status = "Fail" 

	user = 'None'
        print "BAD LOGIN"
        if authlog.AUTHLOG_SAVE_BAD_LOGINS:
	    access = models.Access.objects.create(
	       user = user,
	       user_agent = ua,
	       ip_address = ip,
	       get_data = get,
	       post_data = post, 
	       http_accept = accept, 
	       path_info = path, 
	    )
        return_status = False
    else:
        login_status = "Pass" 
        print "GOOD LOGIN"
        user = request.user

        if authlog.AUTHLOG_SAVE_GOOD_LOGINS:
            access = models.Access.objects.create(
               user = user.username,
               user_agent = ua,
               ip_address = ip,
               get_data = get,
               post_data = post, 
               http_accept = accept, 
               path_info = path, 
            )
        return_status=True

    if authlog.AUTHLOG_LOG_TO_FILE:
        log.info('AUTHLOG: Login %s : ip : %s : path : %s : user : %s ' % (login_status, ip, path, user ) )

    return return_status



