import multiprocessing

bind = '192.168.30.19:25351'
workers = multiprocessing.cpu_count() * 2 + 1 # why
accesslog = '/home/radmin/Documents/api_excel/v3/logs/access.log'
errorlog = '/home/radmin/Documents/api_excel/v3/logs/error.log'
loglevel = 'info'

capture_output = True
