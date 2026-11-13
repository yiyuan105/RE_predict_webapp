from django.apps import AppConfig
import os

class RePredictWebappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'RE_predict_webapp'

    def ready(self):
        from .models_loader import load_models
        if os.environ.get('RUN_MAIN', None) != 'true' and os.environ.get('WERKZEUG_RUN_MAIN', None) != 'true':
            pass
        
        load_models()