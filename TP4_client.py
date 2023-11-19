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


class Client:
    """Client pour le serveur mail @glo2000.ca."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((destination, gloutils.APP_PORT))
        self._username = ""

    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        username = input("Entrez un nom d'utilisateur: ")
        password = getpass.getpass("Entrez un mot de passe: ")
        authHeader = gloutils.AuthPayload(username=username, password=password)
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_REGISTER, payload=authHeader)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._get_response()
        if data["header"] == gloutils.Headers.OK:
            self._username = username



    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        username = input("Entrez votre nom d'utilisateur: ")
        password = getpass.getpass("Entrez votre mot de passe: ")
        authHeader = gloutils.AuthPayload(username=username, password=password)
        message = gloutils.GloMessage(header=gloutils.Headers.AUTH_LOGIN, payload=authHeader)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._get_response()
        if data["header"] == gloutils.Headers.OK:
            self._username = username


    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
    
    def _display_email(self, nb_email: int) -> None:
        choice = input("Entrez votre choix [1-{}] : ".format(nb_email))
        emailChoiceHeader = gloutils.EmailChoicePayload(choice=choice)
        message = gloutils.GloMessage(header=gloutils.Headers.INBOX_READING_CHOICE, payload=emailChoiceHeader)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._get_response()
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
        data = self._get_response()
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
        destination = input("Entrez l'adresse du destinataire: ")
        subject = input("Entrez le sujet: ")
        content_list = []
        print("Entrez le contenu du courriel, terminez la saisie avec un '.' seul sur une ligne: ")
        while True:
            content = input()
            if content == ".":
                break
            content_list.append(content)
        content = "\n".join(content_list)
        current_time = gloutils.get_current_utc_time()
        emailHeader = gloutils.EmailContentPayload(sender=self._username, destination=destination, subject=subject, date=current_time, content=content)
        message = gloutils.GloMessage(header=gloutils.Headers.EMAIL_SENDING, payload=emailHeader)
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._get_response()

    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        message = gloutils.GloMessage(header=gloutils.Headers.STATS_REQUEST, payload={})
        glosocket.send_mesg(self._socket, json.dumps(message))
        data = self._get_response()
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


    
    def _get_response(self) -> gloutils.GloMessage:
        data = glosocket.recv_mesg(self._socket)
        data_json = json.loads(data)
        if data_json["header"] == gloutils.Headers.ERROR:
            print(data_json["payload"]["error_message"])
        return data_json


    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:

            if not self._username:
                # Authentication menu
                print(gloutils.CLIENT_AUTH_CHOICE)
                choice = input("Entre votre choix [1-3]: ")
                match choice:
                    case "1":
                        self._register()
                    case "2":
                        self._login()
                    case "3":
                        exit(0)
                pass
            else:
                print(gloutils.CLIENT_USE_CHOICE)
                choice = input("Entre votre choix [1-4]: ")
                match choice:
                    case "1":
                        print("READ EMAIL")
                        self._read_email()
                    case "2":
                        print("SEND EMAIL")
                        self._send_email()
                    case "3":
                        print("CHECK STATS")
                        self._check_stats()
                    case "4":
                        print("LOGOUT")
                        self._logout()
                pass
            


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
