import os
import time

import configuration

start = time.time()
while time.time() - start < 30:
    all_pidfiles_exist = True
    for service in configuration.services.SERVICEMANAGER["services"]:
        if not os.path.exists(service["pidfile_path"]):
            all_pidfiles_exist = False
    if all_pidfiles_exist:
        break
    else:
        time.sleep(0.1)
