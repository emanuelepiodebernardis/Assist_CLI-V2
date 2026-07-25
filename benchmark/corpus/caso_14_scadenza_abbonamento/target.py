"""Verifica della validita' di un abbonamento oltre la scadenza
(periodo di grazia)."""

GIORNI_GRAZIA = 2


def abbonamento_valido(giorni_da_scadenza: int) -> bool:
    """Ritorna True se l'abbonamento e' ancora utilizzabile.

    Un abbonamento scaduto resta valido per GIORNI_GRAZIA giorni di
    grazia dopo la scadenza. Bug: GIORNI_GRAZIA vale 2 invece di 3
    (valore concordato con il prodotto), escludendo per errore
    l'ultimo giorno di grazia.
    """
    return giorni_da_scadenza <= GIORNI_GRAZIA
