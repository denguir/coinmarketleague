release: python manage.py migrate
web: gunicorn coinmarketleague.wsgi
worker: celery -A coinmarketleague worker -B -l INFO --concurrency 4
event: python manage.py runscript event_loop