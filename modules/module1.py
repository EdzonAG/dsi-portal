import os
import json
import tempfile
import tweepy
import facebook
import requests
import uuid # Necesario para nombres únicos temporales
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from models import Module, module_permission_required

module1_bp = Blueprint('publisher', __name__, template_folder='../templates')

def cargar_config():
    config_path = os.path.join(current_app.instance_path, 'tokens.json')
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config
    except Exception as e:
        flash(f"Error al cargar la configuración: {e}", "danger")
        return None

def publicar_twitter(mensaje, imagenes_paths, twitter):
    """
    imagenes_paths: lista de rutas de archivos
    """
    if not twitter:
        return "❌ Twitter desactivado"
    config = cargar_config()
    if not config:
        return "❌ No se pudo cargar la configuración"
    
    try:
        # Autenticación API v2 (Client) y v1.1 (API)
        client = tweepy.Client(
            consumer_key=config["CONSUMER_KEY"],
            consumer_secret=config["CONSUMER_SECRET"],
            access_token=config["ACCESS_TOKEN"],
            access_token_secret=config["ACCESS_TOKEN_SECRET"]
        )
        api_twitter = tweepy.API(tweepy.OAuth1UserHandler(
            config["CONSUMER_KEY"],
            config["CONSUMER_SECRET"],
            config["ACCESS_TOKEN"],
            config["ACCESS_TOKEN_SECRET"]
        ), wait_on_rate_limit=True)

        media_ids = []
        if imagenes_paths:
            # Twitter permite máximo 4 imágenes por tweet
            paths_to_upload = imagenes_paths[:4] 
            for path in paths_to_upload:
                media = api_twitter.media_upload(path)
                media_ids.append(media.media_id)
        
        if media_ids:
            client.create_tweet(text=mensaje, media_ids=media_ids)
        else:
            client.create_tweet(text=mensaje)
            
        estado_tw = "✅ Twitter publicado"
    except Exception as e:
        estado_tw = f"❌ Error Twitter: {e}"
    
    return estado_tw

def publicar_fb(mensaje, imagenes_paths, facebook_b):
    if not facebook_b:
        return "❌ Facebook desactivado"
    config = cargar_config()
    
    # Asegúrate de usar la clave correcta (ej. FACEBOOK_ACCESS_TOKEN o access_token)
    fb_token = config.get("FACEBOOK_ACCESS_TOKEN") or config.get("access_token")
    if not fb_token:
        return "❌ No se pudo cargar el token de Facebook"

    try:
        api_facebook = facebook.GraphAPI(fb_token)
        
        if imagenes_paths:
            # Lista temporal para guardar los objetos (diccionarios), NO strings
            media_objects = []
            
            for path in imagenes_paths:
                with open(path, "rb") as img_file:
                    # 1. Subir la foto sin publicarla en el feed (published=False)
                    photo = api_facebook.put_photo(image=img_file, published=False)
                    
                    # 2. Agregar el diccionario a nuestra lista
                    # Nota: NO usamos json.dumps aquí adentro individualmente
                    media_objects.append({'media_fbid': photo['id']})
            
            # 3. Convertimos la lista completa de objetos a un string JSON
            attached_media_json = json.dumps(media_objects)
            
            # 4. Enviamos ese string JSON
            api_facebook.put_object(
                parent_object='me', 
                connection_name='feed', 
                message=mensaje, 
                attached_media=attached_media_json
            )
        else:
            api_facebook.put_object(parent_object='me', connection_name='feed', message=mensaje)
            
        estado_fb = "✅ Facebook publicado"
    except Exception as e:
        estado_fb = f"❌ Error Facebook: {e}"

    return estado_fb

def notificar_telegram(texto):
    config = cargar_config()
    if not config:
        return
    # Nota: Verifica si tu IP de Telegram (149...) es correcta o usa api.telegram.org directamente
    for chat_id in config["CHAT_IDS"]:
        url = f"https://api.telegram.org/bot{config['TOKEN_TELEGRAM']}/sendMessage"
        params = {'chat_id': chat_id, 'text': texto}
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Usamos print o logging aquí para no romper el flujo principal con flash si esto falla en segundo plano
            print(f"Error Telegram: {e}")

@module1_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('publisher')
def publisher_home():
    if request.method == 'POST':
        mensaje = request.form.get('mensaje')
        if not mensaje or len(mensaje) > 270:
            flash("El mensaje es obligatorio y no puede exceder 270 caracteres.", "danger")
            return redirect(url_for('publisher.publisher_home'))
        
        # Obtener lista de archivos
        imagenes = request.files.getlist('imagen')
        imagenes_paths = []
        temp_dir = tempfile.gettempdir()

        # Procesar imágenes si existen y tienen nombre
        if imagenes and imagenes[0].filename != "":
            for img in imagenes:
                if img.filename == "": continue
                # Usar UUID para evitar colisión de nombres si suben 2 archivos iguales
                ext = os.path.splitext(img.filename)[1]
                safe_name = f"{secure_filename(os.path.splitext(img.filename)[0])}_{uuid.uuid4().hex}{ext}"
                path = os.path.join(temp_dir, safe_name)
                img.save(path)
                imagenes_paths.append(path)
        
        facebook_active = True if request.form.get('facebook') == 'on' else False
        twitter_active = True if request.form.get('twitter') == 'on' else False
        
        estado_tw = publicar_twitter(mensaje, imagenes_paths, twitter_active)
        estado_fb = publicar_fb(mensaje, imagenes_paths, facebook_active)
        
        # Limpieza de archivos temporales (opcional pero recomendado)
        for path in imagenes_paths:
            try:
                os.remove(path)
            except:
                pass

        resumen = f"Publicación realizada:\nTwitter: {estado_tw}\nFacebook: {estado_fb}"
        notificar_telegram(resumen + f"\nMensaje: {mensaje}")
        flash(resumen, "success")
        return redirect(url_for('publisher.publisher_home'))
        
    return render_template('module1.html', show_sidebar=True, modules=Module.query.all(), module_name = Module.query.filter_by(identifier='publisher').first().title)