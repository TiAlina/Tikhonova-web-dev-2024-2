import mysql.connector
from flask import g


class DatabaseConnector:
    def __init__(self, app):
        self.app = app
        app.teardown_appcontext(self.close_database)

    def config(self):
        config_dictionary = {
            'host': self.app.config['MYSQL_HOST'],
            'database': self.app.config['MYSQL_DATABASE'],
            'user': self.app.config['MYSQL_USER'],
            'password': self.app.config['MYSQL_PASSWORD']
        }
        return config_dictionary

    def connect(self):
        if 'database' not in g:
            g.database = mysql.connector.connect(**self.config())
        return g.database

    def close_database(self, e=None):
        database = g.pop('database', None)
        if database is not None:
            database.close()