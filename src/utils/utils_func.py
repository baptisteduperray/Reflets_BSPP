import time
from functools import wraps

# Décorateur permettant de mesurer la durée d'une fonction 
#@timer
#def algo():
#   time.sleep(10)
#   return "fin"
#
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"Durée d'exécution : {func.__name__}: {end - start:.4f} secondes")
        return result
    return wrapper
