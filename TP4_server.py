"""\
GLO-2000 Travail pratique 4 - Serveur
Noms et numéros étudiants:
-
-
-
"""

import hashlib
import hmac
import json
import os
import select
import socket
import sys
import re
from typing import Dict

import glosocket
import gloutils


class Server:
    """Serveur mail @glo2000.ca."""

    def __init__(self) -> None:
        """
        Prépare le socket du serveur `_server_socket`
        et le met en mode écoute.

        Prépare les attributs suivants:
        - `_client_socs` une liste des sockets clients.
        - `_logged_users` un dictionnaire associant chaque
            socket client à un nom d'utilisateur.

        S'assure que les dossiers de données du serveur existent.
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self._server_socket.bind(("127.0.0.1", gloutils.APP_PORT))
        self._server_socket.listen(1)
        self._client_socs : List[socket.socket] = [] 
        self._logged_users : Dict[socket.socket, str] = {}
        if (os.path.exists(gloutils.SERVER_DATA_DIR) is False):
            os.mkdir(gloutils.SERVER_DATA_DIR)
            os.mkdir(gloutils.SERVER_DATA_DIR + "/" + gloutils.SERVER_LOST_DIR)
        if (os.path.exists(gloutils.SERVER_DATA_DIR + "/" + gloutils.SERVER_LOST_DIR) is False):  # noqa: E501
            os.mkdir(gloutils.SERVER_DATA_DIR + "/" + gloutils.SERVER_LOST_DIR)
        self._mail_list = []
        # ...

    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            client_soc.close()
        self._server_socket.close()

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        client_soc, _ = self._server_socket.accept()
        self._client_socs.append(client_soc)
        print("Un nouveau client est connecté")

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        if client_soc in self._client_socs:
            self._client_socs.remove(client_soc)
        if client_soc in self._logged_users:
            self._logged_users.pop(client_soc)
        client_soc.close()


    def _is_alphanumeric(self, string):
        return bool(re.match(r'^[a-zA-Z0-9_.-]+$', string))

    def _password_valid(self, string):
        # avoir une taille supérieure ou égale à 10 caractères, contenir au moins un chiffre, uneminuscule et une majuscule.
        return bool(re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9]).{10,}$', string))

    def _create_account(self, client_soc: socket.socket,
                        payload: gloutils.AuthPayload
                        ) -> gloutils.GloMessage:
        """
        Crée un compte à partir des données du payload.

        Si les identifiants sont valides, créee le dossier de l'utilisateur,
        associe le socket au nouvel l'utilisateur et retourne un succès,
        sinon retourne un message d'erreur.
        """
        error_message = []
        # check username is alphanumeric _ . -
        if not self._is_alphanumeric(payload["username"]):
            error_message.append("- Le nom d'utilisateur est invalide.")
        # check username already exist
        if os.path.exists(gloutils.SERVER_DATA_DIR + "/" + payload["username"]):
            error_message.append("- Le nom d'utilisateur est déjà utilisé")
        # check password length
        if not self._password_valid(payload["password"]):
            error_message.append("- Le mot de passe n'est pas assez sûr.")
        if len(error_message) > 0:
            error_message.insert(0, "La création a échouée:")
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="\n".join(error_message)))
            return message
        # create folder
        os.mkdir(gloutils.SERVER_DATA_DIR + "/" + payload["username"])
        # hash password sha3_512 in filte PASSWORD_FILENAME
        password_hash = hashlib.sha3_512(payload["password"].encode()).hexdigest()
        # create file PASSWORD_FILENAME in folder
        with open(gloutils.SERVER_DATA_DIR + "/" + payload["username"] + "/" + gloutils.PASSWORD_FILENAME, "w") as file:
            file.write(password_hash)
        # create folder INBOX to store email
        os.mkdir(gloutils.SERVER_DATA_DIR + "/" + payload["username"] + "/INBOX")
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK)
        self._logged_users[client_soc] = payload["username"]
        return message

    def _login(self, client_soc: socket.socket, payload: gloutils.AuthPayload
               ) -> gloutils.GloMessage:
        """
        Vérifie que les données fournies correspondent à un compte existant.

        Si les identifiants sont valides, associe le socket à l'utilisateur et
        retourne un succès, sinon retourne un message d'erreur.
        """
        # check if username exist
        if not os.path.exists(gloutils.SERVER_DATA_DIR + "/" + payload["username"]):
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Nom d'utilisateur ou mot de passe invalide."))
            return message
        # check password from username
        with open(gloutils.SERVER_DATA_DIR + "/" + payload["username"] + "/" + gloutils.PASSWORD_FILENAME, "r") as file:
            password_hash = file.read()
        if password_hash != hashlib.sha3_512(payload["password"].encode()).hexdigest():
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Nom d'utilisateur ou mot de passe invalide."))
            return message
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK)
        self._logged_users[client_soc] = payload["username"]
        return message

    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        if client_soc in self._logged_users:
            self._logged_users.pop(client_soc)
            print("Le client a été déconnecté")
        else:
            print("Le client n'est pas connecté")
    
    def _convert_email_list(self, email_list: list[Dict]) -> list[str]:
        """
        Convertir une liste de courriels en une liste de SUBJECT_DISPLAY.
        """
        ret = []
        for i in range (len(email_list)):
            ret.append(gloutils.SUBJECT_DISPLAY.format(
                number=i + 1,
                sender=email_list[i]["sender"],
                subject=email_list[i]["subject"],
                date=email_list[i]["date"]
            ))

        return ret

    def _get_email_list(self, client_soc: socket.socket
                        ) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        # get list of email in folder INBOX
        email_list = os.listdir(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX")
        # sort email_list by date
        email_list.sort(key=lambda x: os.path.getmtime(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX/" + x), reverse=True)
        # read each email and get content of file
        email_list_content = []
        for email in email_list:
            with open(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX/" + email, "r") as file:
                email_list_content.append(self._parse_email(file))
        display_list = self._convert_email_list(email_list_content)
        self._mail_list = email_list
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK, payload=gloutils.EmailListPayload(email_list=display_list))
        return message

    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        # check if choice is valid
        if int(payload["choice"]) < 1 or int(payload["choice"]) > len(self._mail_list):
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Le choix n'est pas valide"))
            return message
        # read email
        with open(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX/" + self._mail_list[int(payload["choice"]) - 1], "r") as file:
            mail_parse = self._parse_email(file)
        mail = gloutils.EMAIL_DISPLAY.format(
            sender=mail_parse["sender"],
            to=mail_parse["destination"],
            subject=mail_parse["subject"],
            date=mail_parse["date"],
            body=mail_parse["content"]
        )
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK, payload=gloutils.EmailContentPayload(email=mail))
        return message

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        # get number of email
        email_list = os.listdir(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX")
        nb_email = len(email_list)
        # get size of folder
        size = 0
        for email in email_list:
            size += os.path.getsize(gloutils.SERVER_DATA_DIR + "/" + self._logged_users[client_soc] + "/INBOX/" + email)
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK, payload=gloutils.StatsPayload(count=nb_email, size=size))

        return message
    
    def _write_message(self, file, payload: gloutils.EmailContentPayload) -> None:
        file.write("FROM: " + payload["sender"] + "\n")
        file.write("TO: " + payload["destination"] + "\n")
        file.write("SUBJECT: " + payload["subject"] + "\n")
        file.write("DATE: " + payload["date"] + "\n")
        file.write("\n")
        file.write(payload["content"])
    
    def _parse_email(self, file) -> gloutils.EmailContentPayload:
        payload = gloutils.EmailContentPayload()
        payload["sender"] = file.readline()[6:-1]
        payload["destination"] = file.readline()[4:-1]
        payload["subject"] = file.readline()[9:-1]
        payload["date"] = file.readline()[6:-1]
        file.readline()
        payload["content"] = file.read()
        return payload

    def _parse_email_address(self, email_address: str) -> tuple[str, bool]:
        # parse mail address @
        if "@" not in email_address:
            return ("", False)
        # get username and domain
        username, domain = email_address.split("@")
        # compare domain with glo2000.ca
        if domain != gloutils.SERVER_DOMAIN:
            return (username, True)
        return (username, False)

    def _send_email(self, payload: gloutils.EmailContentPayload
                    ) -> gloutils.GloMessage:
        """
        Détermine si l'envoi est interne ou externe et:
        - Si l'envoi est interne, écris le message tel quel dans le dossier
        du destinataire.
        - Si le destinataire n'existe pas, place le message dans le dossier
        SERVER_LOST_DIR et considère l'envoi comme un échec.
        - Si le destinataire est externe, considère l'envoi comme un échec.

        Retourne un messange indiquant le succès ou l'échec de l'opération.
        """
        destination, is_external = self._parse_email_address(payload["destination"])
        # check if external
        if is_external:
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Le destinataire est externe"))
            return message
        # check if destination exist
        if not os.path.exists(gloutils.SERVER_DATA_DIR + "/" + destination):
            # write message in SERVER_LOST_DIR
            with open(gloutils.SERVER_DATA_DIR + "/" + gloutils.SERVER_LOST_DIR + "/" + destination + "_" + payload["date"].replace(":", "-"), "w") as file:
                self._write_message(file, payload)
            # ERROR message
            message = gloutils.GloMessage(header=gloutils.Headers.ERROR, payload=gloutils.ErrorPayload(error_message="Le destinataire n'existe pas"))
            return message
        # write message in destination folder sender
        with open(gloutils.SERVER_DATA_DIR + "/" + destination + "/INBOX/" + payload["sender"] + "_" + payload["date"].replace(":", "-"), "w") as file:
            self._write_message(file, payload)
        # OK message
        message = gloutils.GloMessage(header=gloutils.Headers.OK)
        return message
    
    def _function_ptr(self, data_json: dict[str, str], client_soc: socket.socket) -> None:
        header = gloutils.Headers
        message = None
        print("")
        match data_json["header"]:
            case header.AUTH_LOGIN:
                print("LOGIN")
                message = self._login(client_soc, data_json["payload"])
            case header.AUTH_REGISTER:
                print("REGISTER")
                message = self._create_account(client_soc, data_json["payload"])
            case header.AUTH_LOGOUT:
                print("LOGOUT")
                message = self._logout(client_soc)
            case header.INBOX_READING_REQUEST:
                print("INBOX_READING_REQUEST")
                message = self._get_email_list(client_soc)
            case header.INBOX_READING_CHOICE:
                print("INBOX_READING_CHOICE")
                message = self._get_email(client_soc, data_json["payload"])
            case header.EMAIL_SENDING:
                print("EMAIL_SENDING")
                message = self._send_email(data_json["payload"])
            case header.STATS_REQUEST:
                print("STATS_REQUEST")
                message = self._get_stats(client_soc)
        if message != None:
            glosocket.send_mesg(client_soc, json.dumps(message))



    def run(self):
        """Point d'entrée du serveur."""
        waiters = []
        while True:
            # Select readable sockets
            waiters, _, _ = select.select([self._server_socket] + self._client_socs, [], [])
            for waiter in waiters:
                # Handle sockets
                if waiter is self._server_socket:
                    self._accept_client()
                    continue
                try: 
                    data = glosocket.recv_mesg(waiter)
                    # data to json
                    data_json = json.loads(data)
                    # pointer to function
                    self._function_ptr(data_json, waiter)
                except glosocket.GLOSocketError:
                    self._remove_client(waiter)
                    continue
                    



def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
