from flask import Blueprint, request, jsonify
from services import whatsapp_service

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route('/webhook', methods=['GET'])
def webhook_verify():
    """Verify WhatsApp webhook"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    result, status_code = whatsapp_service.verify_webhook(mode, token, challenge)
    return result, status_code


@chat_bp.route('/webhook', methods=['POST'])
def webhook_receive():
    """Handle incoming WhatsApp messages"""
    # Skip signature verification for now (enable in production)
    # signature = request.headers.get('X-Hub-Signature-256')
    # if signature and not whatsapp_service.verify_signature(request.data, signature):
    #     print("❌ Invalid signature")
    #     return jsonify({'error': 'Invalid signature'}), 403
    
    data = request.get_json()
    
    result = whatsapp_service.process_webhook_event(data)
    return jsonify({'status': result}), 200


@chat_bp.route('/place-order', methods=['POST'])
def place_order():
    """Place an order via WhatsApp"""
    from services import SupabaseService
    db_service = SupabaseService()
    
    raw_data = request.get_json()
    
    if raw_data is None:
        return jsonify({'error': 'No JSON data provided'}), 400
    if 'args' in raw_data:
        data = raw_data['args']
    else:
        data = raw_data
    if data is None:
        return jsonify({'error': 'No order data provided'}), 400
    
    required_fields = ['items', 'delivery_address', 'phone_number']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
    
    items = data['items']
    delivery_address = data['delivery_address']
    customer_phone_number = data['phone_number']
    special_requests = data.get('special_requests')
    
    order_id = db_service.place_order(items, delivery_address, customer_phone_number, special_requests)
    
    if order_id:
        return jsonify({'order_id': order_id, 'message': 'Order placed successfully'}), 201
    else:
        return jsonify({'error': 'Failed to place order'}), 500


@chat_bp.route('/order-status', methods=['GET'])
def get_order_status():
    """Get order/delivery status for WhatsApp user"""
    from services import SupabaseService
    db_service = SupabaseService()
    
    phone_number = request.args.get('phone_number')
    
    if not phone_number:
        return jsonify({'error': 'phone_number is required'}), 400
    
    orders = db_service.get_order_status(phone_number)
    return jsonify(orders)


@chat_bp.route('/notify-status', methods=['POST'])
def notify_order_status():
    """Send WhatsApp notification when order status changes"""
    from services import SupabaseService
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'error': 'order_id is required'}), 400
    
    db_service = SupabaseService()
    
    # Fetch order details
    order_response = db_service.supabase.table('orders').select('*').eq('order_id', order_id).single().execute()
    
    if not order_response.data:
        return jsonify({'error': 'Order not found'}), 404
    
    order = order_response.data
    phone_number = order.get('customer_phone_number')
    status = order.get('status')
    
    if not phone_number:
        return jsonify({'error': 'No phone number for this order'}), 400
    
    # Format items
    items_dict = order.get('items', {})
    items_list = []
    for item_id, quantity in items_dict.items():
        menu_item = db_service.supabase.table('menu').select('name').eq('item_id', int(item_id)).execute()
        if menu_item.data:
            item_name = menu_item.data[0]['name']
            if quantity > 1:
                items_list.append(f"{item_name} x{quantity}")
            else:
                items_list.append(item_name)
    
    items_text = ', '.join(items_list) if items_list else 'your order'
    
    # Create message based on status
    if status == 'ON_ROUTE':
        message = f"Your order of {items_text} is on route to {order.get('delivery_address')}. It will arrive shortly."
    elif status == 'DELIVERED':
        message = f"Your order of {items_text} has been delivered. Enjoy your food!"
    else:
        message = f"Your order of {items_text} status has been updated to {status}."
    
    # Send WhatsApp message
    try:
        whatsapp_service.send_message(phone_number, message)
        print(f"✅ Status notification sent to {phone_number}")
        return jsonify({'message': 'Notification sent successfully'}), 200
    except Exception as e:
        print(f"❌ WhatsApp error: {e}")
        return jsonify({'error': str(e)}), 500
