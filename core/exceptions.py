class AppError(Exception):
    """Base de todas las excepciones de la aplicación."""

class ReglaNegocioViolada(AppError): pass
class RecursoNoEncontrado(AppError): pass
class AccesoNoAutorizado(AppError): pass
