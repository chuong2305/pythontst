from time import time

def add_timestamp(request):
    return {"timestamp": int(time())}
