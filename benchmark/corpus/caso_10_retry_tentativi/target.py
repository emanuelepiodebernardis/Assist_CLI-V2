"""Politica di retry: numero massimo di tentativi per un'operazione."""


def puo_tentare_ancora(tentativo_corrente: int, max_tentativi: int = 5) -> bool:
    """Ritorna True se si puo' ancora tentare l'operazione.

    I tentativi sono numerati da 0. Bug: usa ``<=`` invece di ``<``,
    permettendo un tentativo in piu' rispetto al limite configurato.
    """
    return tentativo_corrente <= max_tentativi
