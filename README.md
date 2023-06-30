# django-dashboards
Django project to create dashboards with columns and tasks 

Quick start
-----------

1. Clone repo  like this::

      git clone  git@github.com:dimkoug/django-dashboards.git

2. Create a virtualenv::

    python3 -m venv .venv

3. Activate virtualenv

4. Install packages from requirements.txt file

5. Create settings_local.py with settings from settings_local_sample.py

6. In settings_local configure the database and the gdal path 

7. Run `python manage.py makemigrations`

8. Run `python manage.py migrate`

9. Run `python manage.py createsuperuser`

10. Start the development server and visit http://127.0.0.1:8000/