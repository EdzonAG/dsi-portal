# modules/module2.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import Module, module_permission_required
from modules.module1 import cargar_config
import requests
import datetime
import json

module2_bp = Blueprint('tokens', __name__, template_folder='../templates')

def obtener_info_token(access_token):
    url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": access_token,
        "access_token": access_token,
        }
    response = requests.get(url, params=params)
    data = response.json()
    if "data" in data and data["data"].get("is_valid"):
        utc_time = datetime.datetime.fromtimestamp(data["data"]["expires_at"], datetime.timezone.utc)
        mexico_city_time = utc_time.astimezone(datetime.timezone(datetime.timedelta(hours=-6)))
        expires_at = mexico_city_time.strftime('%d-%m-%Y %H:%M:%S')
    else:
        expires_at = 'Token expirado o no válido'
    return expires_at

def actualizar_tokens(token_fb, token_x_1, token_x_2, token_x_3, token_x_4, token_telegram, chat_ids, token_openai):
    config = cargar_config()
    config["access_token"] = token_fb
    config["CONSUMER_KEY"] = token_x_1
    config["CONSUMER_SECRET"] = token_x_2
    config["ACCESS_TOKEN"] = token_x_3
    config["ACCESS_TOKEN_SECRET"] = token_x_4
    config["TOKEN_TELEGRAM"] = token_telegram
    config["CHAT_IDS"] = chat_ids.replace(" ", "").split(",")
    config["openai_api_key"] = token_openai
    with open("./instance/tokens.json", 'w') as f:
        json.dump(config, f, indent=4)

@module2_bp.route('/', methods=['GET', 'POST'])
@login_required
@module_permission_required('tokens')
def tokens_home():
    config = cargar_config()
    token_fb = config["access_token"]
    token_x_1 = config["CONSUMER_KEY"]
    token_x_2 = config["CONSUMER_SECRET"]
    token_x_3 = config["ACCESS_TOKEN"]
    token_x_4 = config["ACCESS_TOKEN_SECRET"]
    token_telegram = config["TOKEN_TELEGRAM"]
    chat_ids = config["CHAT_IDS"]
    token_openai = config["openai_api_key"]
    date_fb = obtener_info_token(token_fb)
    chat_ids_str = ""
    
    for chat_id in chat_ids:
        chat_ids_str += f"{chat_id},"
    chat_ids_str = chat_ids_str[:-1]
    
    if request.method == 'POST':
        try:
            token_fb = request.form.get('facebook-token')
            token_x_1 = request.form.get('twitter-token_1')
            token_x_2 = request.form.get('twitter-token_2')
            token_x_3 = request.form.get('twitter-token_3')
            token_x_4 = request.form.get('twitter-token_4')
            token_telegram = request.form.get('telegram-token')
            chat_ids = request.form.get('telegram-chatid')
            token_openai = request.form.get('openai-token')
            actualizar_tokens(token_fb, token_x_1, token_x_2, token_x_3, token_x_4, token_telegram, chat_ids, token_openai)
            flash(f"Tokens actualizados correctamente", "success")
            return redirect(url_for('tokens.tokens_home'))
        except Exception as e:
            flash(f"Error al actualizar tokens: {e}", "danger")
    return render_template('module2.html',
                            token_fb=token_fb,
                            token_x_1=token_x_1,
                            token_x_2=token_x_2,
                            token_x_3=token_x_3,
                            token_x_4=token_x_4,
                            token_telegram=token_telegram,
                            chat_ids=chat_ids_str,
                            token_openai=token_openai,
                            date_fb=date_fb,
                            show_sidebar=True,
                            modules=Module.query.all())