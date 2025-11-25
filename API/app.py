import logging
from flask import Flask, jsonify
from flask_cors import CORS
from controllers import chat_bp, call_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(chat_bp)
app.register_blueprint(call_bp)

@app.route('/health', methods=['GET'])
def health_check():
    from services import whatsapp_service, phone_number_service
    
    return jsonify({
        'status': 'healthy',
        'active_whatsapp_sessions': whatsapp_service.get_active_sessions_count(),
        'active_call_sessions': phone_number_service.get_active_sessions_count()
    }), 200


if __name__ == '__main__':

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(debug=True, port=5000)