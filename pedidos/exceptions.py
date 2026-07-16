from core.exceptions import ReglaNegocioViolada

class ProductoSinStock(ReglaNegocioViolada): pass
class NegocioCerrado(ReglaNegocioViolada): pass
class TransicionInvalida(ReglaNegocioViolada): pass
class CarritoVacio(ReglaNegocioViolada): pass
class CuponInvalido(ReglaNegocioViolada): pass
