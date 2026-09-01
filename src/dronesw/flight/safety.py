# flight/safety.py: Un hilo en segundo plano que corre en paralelo a la par del ejecutor.
# Vigila cada segundo el nivel de batería y el rango de señal. Si algo sale mal, interrumpe
# al ejecutor y fuerza un aterrizaje.
# TODO: implementar (ver PLANNING.md)
