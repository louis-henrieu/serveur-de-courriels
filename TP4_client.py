"""\
GLO-2000 Travail pratique 4 - Client
Noms et numéros étudiants:
-
-
-
"""

import argparse
import getpass
import json
import socket
import sys

import glosocket
import gloutils

class GenericFunction:
    def __init__(self, socket: socket.socket) -> None:
        self._socket = socket
        pass

    def message(self, header: gloutils.Headers, payload: dict) -> gloutils.GloMessage:
        return gloutils.GloMessage(header=header, payload=payload)

    def getUserLoginInfo(self, enum: int) -> tuple[gloutils.GloMessage, str]:
        username = input("Entrez votre nom d'utilisateur: ")
        password = getpass.getpass("Entrez votre mot de passe: ")
        payload = gloutils.AuthPayload(username=username, password=password)
        message = self.message(enum, payload)
        return message, username
    
    def multipleInput(self) -> str:
        content_list = []
        while True:
            content = input()
            if content == ".":
                break
            content_list.append(content)
        content = "\n".join(content_list)
        return content
    
    def createEmail(self, username) -> gloutils.GloMessage:
        destination = input("Entrez l'adresse du destinataire: ")
        subject = input("Entrez le sujet: ")
        content_list = []
        print("Entrez le contenu du courriel, terminez la saisie avec un '.' seul sur une ligne: ")
        content = self.multipleInput()
        current_time = gloutils.get_current_utc_time()
        emailHeader = gloutils.EmailContentPayload(sender=username, destination=destination, subject=subject, date=current_time, content=content)
        message = self.message(gloutils.Headers.EMAIL_SENDING, emailHeader)
        return message
    
    def getResponse(self) -> gloutils.GloMessage:
        try:
            data = glosocket.recv_mesg(self._socket)
            data_json = json.loads(data)
            if data_json["header"] == gloutils.Headers.ERROR:
                print(data_json["payload"]["error_message"])
            return data_json
        except glosocket.GLOSocketError:
            raise "Error : Impossible to get server response"
            exit(-1)

class Client:
    """Client pour le serveur mail @glo2000.ca."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((destination, gloutils.APP_PORT))
        except OSError:
            raise "ERROR : Impossible to create socket"
            exit(-1)
        self._username = ""
        self._genericFunction = GenericFunction(self._socket)

    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        message, username = self._genericFunction.getUserLoginInfo(gloutils.Headers.AUTH_REGISTER)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()
        if data["header"] == gloutils.Headers.OK:
            self._username = username

    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        message, username = self._genericFunction.getUserLoginInfo(gloutils.Headers.AUTH_LOGIN)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()
        if data["header"] == gloutils.Headers.OK:
            self._username = username


    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
        message = self._genericFunction.message(gloutils.Headers.BYE, {})
        glosocket.send_mesg(self._socket, json.dumps(message))
        self._socket.close()
    
    def _display_email(self, nb_email: int) -> None:
        choice = input("Entrez votre choix [1-{}] : ".format(nb_email))
        emailChoiceHeader = gloutils.EmailChoicePayload(choice=choice)
        message = gloutils.GloMessage(header=gloutils.Headers.INBOX_READING_CHOICE, payload=emailChoiceHeader)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()
        if data["header"] == gloutils.Headers.OK:
            print(data["payload"]["email"])


    def _read_email(self) -> None:
        """
        Demande au serveur la liste de ses courriels avec l'entête
        `INBOX_READING_REQUEST`.

        Affiche la liste des courriels puis transmet le choix de l'utilisateur
        avec l'entête `INBOX_READING_CHOICE`.

        Affiche le courriel à l'aide du gabarit `EMAIL_DISPLAY`.

        S'il n'y a pas de courriel à lire, l'utilisateur est averti avant de
        retourner au menu principal.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.INBOX_READING_REQUEST, payload={})
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()
        if data["header"] == gloutils.Headers.OK:
            if len(data["payload"]["email_list"]) == 0:
                print("Vous n'avez aucun mail à lire")
            else:
                for i in range(len(data["payload"]["email_list"])):
                    print(data["payload"]["email_list"][i])
                self._display_email(len(data["payload"]["email_list"]))
            

    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """
        message = self._genericFunction.createEmail(self._username)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()

    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.STATS_REQUEST, payload={})
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._genericFunction.getResponse()
        if data["header"] == gloutils.Headers.OK:
            print(gloutils.STATS_DISPLAY.format(
                count=data["payload"]["count"],
                size=data["payload"]["size"])
                )
        else:
            print("Les statistiques n'ont pas pu être récupérées, veuillez réessayer plus tard")

    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_LOGOUT, payload={})
        glosocket.send_mesg(self._socket, json.dumps(message))
        self._username = ""
    
    def _authChoice(self) -> None:
        print(gloutils.CLIENT_AUTH_CHOICE)
        choice = input("Entre votre choix [1-3]: ")
        match choice:
            case "1":
                self._register()
            case "2":
                self._login()
            case "3":
                self._quit()
                exit(0)
        pass

    def _userChoice(self) -> None:
        print(gloutils.CLIENT_USE_CHOICE)
        choice = input("Entre votre choix [1-4]: ")
        match choice:
            case "1":
                self._read_email()
            case "2":
                self._send_email()
            case "3":
                self._check_stats()
            case "4":
                self._logout()
        pass

    def run(self) -> None:
        """Point d'entrée du client."""
        try:
            should_quit = False

            while not should_quit:
                if not self._username:
                    # Authentication menu
                    self._authChoice()
                else:
                    # User menu
                    self._userChoice()
        except  KeyboardInterrupt as ex:
            self._quit()


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination", action="store",
                        dest="dest", required=True,
                        help="Adresse IP/URL du serveur.")
    args = parser.parse_args(sys.argv[1:])
    client = Client(args.dest)
    client.run()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
