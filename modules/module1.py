import os
import json
import tempfile
import tweepy
import facebook
import requests
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

def publicar_twitter(mensaje, imagen_path, twitter):
    if not twitter:
        return "❌ Twitter desactivado"
    config = cargar_config()
    if not config:
        return "❌ No se pudo cargar la configuración"
    try:
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
        if imagen_path:
            media = api_twitter.media_upload(imagen_path)
            client.create_tweet(text=mensaje, media_ids=[media.media_id])
        else:
            client.create_tweet(text=mensaje)
        estado_tw = "✅ Twitter publicado"
    except Exception as e:
        estado_tw = f"❌ Error Twitter: {e}"
    return estado_tw

def publicar_fb(mensaje, imagen_path, facebook_b):
    if not facebook_b:
        return "❌ Facebook desactivado"
    config = cargar_config()
    if not config:
        return "❌ No se pudo cargar la configuración"

    try:
        api_facebook = facebook.GraphAPI(config["access_token"])
        if imagen_path:
            with open(imagen_path, "rb") as img_file:
                api_facebook.put_photo(img_file, message=mensaje)
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
    for chat_id in config["CHAT_IDS"]:
        url = f"https://149.154.167.220/bot{config["TOKEN_TELEGRAM"]}/sendMessage?chat_id={chat_id}&text={texto}"
        headers = {'Host': 'api.telegram.org'} 
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            flash(f"Error al notificar Telegram: {e}", "danger")

@module1_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('publisher')
def publisher_home():
    if request.method == 'POST':
        mensaje = request.form.get('mensaje')
        if not mensaje or len(mensaje) > 270:
            flash("El mensaje es obligatorio y no puede exceder 270 caracteres.", "danger")
            return redirect(url_for('publisher.publisher_home'))
        imagen = request.files.get('imagen')
        imagen_path = None
        if imagen and imagen.filename != "":
            filename = secure_filename(imagen.filename)
            temp_dir = tempfile.gettempdir()
            imagen_path = os.path.join(temp_dir, filename)
            imagen.save(imagen_path)
        
        facebook = True if request.form.get('facebook') == 'on' else False
        twitter = True if request.form.get('twitter') == 'on' else False
        
        estado_tw = publicar_twitter(mensaje, imagen_path, twitter)
        estado_fb = publicar_fb(mensaje, imagen_path, facebook)
        
        # estado_tw, estado_fb = "✅ Twitter publicado", "✅ Facebook publicado" # Simular publicación
        resumen = f"Publicación realizada:\nTwitter: {estado_tw}\nFacebook: {estado_fb}"
        notificar_telegram(resumen + f"\nMensaje: {mensaje}")
        flash(resumen, "success")
        return redirect(url_for('publisher.publisher_home'))
    return render_template('module1.html', show_sidebar=True, modules=Module.query.all())