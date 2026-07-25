"""Verifica se un utente puo' accedere a un'area riservata per eta'."""


def puo_accedere(eta: int, eta_minima: int = 18) -> bool:
    """Ritorna True se `eta` soddisfa il requisito di `eta_minima`.

    Bug: dovrebbe essere ``eta >= eta_minima`` (chi ha compiuto
    esattamente l'eta' minima deve poter accedere), ma usa ``>``,
    escludendo per errore chi ha esattamente l'eta' minima.
    """
    if eta > eta_minima:
        return True
    return False
