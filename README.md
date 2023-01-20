# Konspekt

## Intro do API

 - userzy tworzą projekty
 - mogą zapraszać innych userów
 - w projekcie są obszary, każdy obszar ma przypisany scenariusz sterowania
 - w obszarach są lampy, które mają być konfigurowane zgodnie ze scenariuszem

### Bebechy

 * bff-svc: API Gateway, uwierzytelnianie, autoryzacja
 * projects-svc: CRUD projektów, obszarów i kolaborantów, autoryzacja
 * node-svc: CRUD lamp
 * config-svc: Generowanie konfiguracji lampy na podstawie scenariusza

### Demo

## ETagi

### Serwer

 Nagłówek `ETag`
 Przechwytywanie odpowiedzi po stronie serwera
 Notka o ASGI
 Generacja hasza
 Zapis

### Klient

 Przechwytywanie odpowiedzi
 Zapis
 Nagłówek `If-None-Match`
 Odczyt i obsługa 304

### Serwer

 Obsługa `If-None-Match` i ominięcie widoku

### Problem: konstrukcja klucza cache

 Nagłówek `Vary`
 Jak go zadeklarować w widoku?

### Problem: inwalidacja cache

 Skąd w widoku znać klucz cache?
 Sygnały: publish
 Sygnały: subscribe + drop

### Problem: żądania inne niż GET

 Nagłówek `Repr-Digest`
 `Vary: Repr-Digest`
 ... and we're done :-o
