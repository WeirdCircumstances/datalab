Das DataLab ist ein Werkzeug zur Vermittlung von Data Literacy. 

### Variablen definieren

Die Datei `.env.template` dient als Vorlage, um die beiden Dateien `.env.dev` und `.env.prod` zu erstellen. Die Felder mit *** müssen mit den passenden Passwörten und Keys versehen werden.

### Entwicklungsumgebung starten

Alle Befehle können mit Podman oder Docker ausgeführt werden.

`docker compose up --build`  

Um das Produktivsystem zu bauen gibt es zwei Möglichkeiten:

**Möglichkeit 1:**  
`docker compose build -f compose-production.yml datalab`  
`docker push <dockerhub_username>/datalab`

**Möglichkeit 2:**  
Die Produktivumgebung kann auch auf dem Zielserver gebaut werden. Dazu müssen alle Projektdateien zuvor auf den Server übertragen werden.
Das Script `./upload.sh` hilft bei diesem Prozess.

`docker compose build -f compose-production.yml datalab`  
   
### Produktivumgebung ausführen

`docker compose -f compose-production.yml up`  
