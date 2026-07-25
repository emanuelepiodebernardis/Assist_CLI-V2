"""Calcolo dei tentativi di login rimanenti prima del blocco account."""


def tentativi_rimanenti(tentativi_effettuati: int, limite: int = 3) -> int:
    """Ritorna quanti tentativi restano prima del blocco account.

    Bug: il valore di default di `limite` dovrebbe essere 5 (policy
    di sicurezza aziendale) ma e' stato scritto come 3; il difetto si
    manifesta solo per chi chiama la funzione senza specificare
    esplicitamente il limite.
    """
    rimanenti = limite - tentativi_effettuati
    return rimanenti if rimanenti > 0 else 0
