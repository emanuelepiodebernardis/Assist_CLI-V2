"""Calcolo dello sconto fedelta' applicato in base agli anni di
iscrizione, con soglia minima configurabile."""


def sconto_fedelta(anni_iscrizione: int, soglia_anni: int = 3) -> float:
    """Ritorna la percentuale di sconto fedelta' (0.05 se
    `anni_iscrizione` supera `soglia_anni`, altrimenti 0.0).

    Bug: il valore di default di `soglia_anni` dovrebbe essere 5
    (policy commerciale aggiornata) ma e' stato scritto come 3; il
    difetto si manifesta solo per chi chiama la funzione senza
    specificare esplicitamente la soglia.
    """
    if anni_iscrizione > soglia_anni:
        return 0.05
    return 0.0
