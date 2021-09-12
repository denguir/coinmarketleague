release: python manage.py migrate
web: gunicorn coinmarketleague.wsgi
event: python manage.py runscript event_loop