"""Controllo permessi per l'eliminazione di una risorsa."""


def puo_eliminare_risorsa(e_admin: bool, e_proprietario: bool) -> bool:
    """Ritorna True se l'utente puo' eliminare la risorsa.

    L'eliminazione e' consentita se l'utente e' admin OPPURE se e'
    il proprietario della risorsa. Bug: usa ``and`` invece di
    ``or``, richiedendo erroneamente che siano vere entrambe le
    condizioni.
    """
    return e_admin and e_proprietario
