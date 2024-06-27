from flask import g
import mysql.connector

class DBConnector:
    def __init__(self, app):
        self.app = app
        app.teardown_appcontext(self.close_connection)
    
    def get_config(self):
        return {
            'user': self.app.config['DB_USER'],
            'password': self.app.config['DB_PASSWORD'],
            'host': self.app.config['DB_HOST'],
            'database': self.app.config['DB_NAME']
        }

    def connect(self):
        if 'db' not in g:
            g.db = mysql.connector.connect(**self.get_config())

        return g.db
    
    def close_connection(self, e=None):
        db = g.pop('db', None)

        if db is not None:
            db.close()