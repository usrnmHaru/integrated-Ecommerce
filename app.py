from flask import Flask, request, jsonify, redirect, url_for, render_template
from flask_admin import Admin, BaseView, AdminIndexView, expose
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///orders.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add custom fromjson filter to Flask's existing Jinja2 environment
def fromjson_filter(v):
    if v and v != 'null':
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

app.jinja_env.filters['fromjson'] = fromjson_filter

# Initialize Flask-Admin
class SecureAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        home_url = url_for('index')
        orders_url = url_for('orderview.index')
        return self.render('admin/index.html', home_url=home_url, orders_url=orders_url)

    def is_accessible(self):
        return True

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('index'))

admin = Admin(app, name='Order Management', template_mode='bootstrap4', index_view=SecureAdminIndexView())
admin.base_template = 'admin/base.html'

# In-memory dictionary for orders
orders_db = {}
next_order_id = 1

# Custom Flask-Admin view for managing orders_db
class OrderView(BaseView):
    @expose('/')
    def index(self):
        home_url = url_for('index')
        orders_url = url_for('orderview.index')
        return self.render('admin/orders.html', orders=orders_db, home_url=home_url, orders_url=orders_url)

    @expose('/edit/<int:order_id>', methods=['GET', 'POST'])
    def edit(self, order_id):
        order = orders_db.get(order_id)
        if not order:
            return redirect(url_for('orderview.index'))
        home_url = url_for('index')
        orders_url = url_for('orderview.index')
        
        if request.method == 'POST':
            # Parse current shipping_info
            current_shipping = {}
            if order.get('shipping_info'):
                try:
                    current_shipping = json.loads(order.get('shipping_info'))
                except (json.JSONDecodeError, TypeError):
                    current_shipping = {}

            # Parse current order_summary
            current_summary = {}
            if order.get('order_summary'):
                try:
                    current_summary = json.loads(order.get('order_summary'))
                except (json.JSONDecodeError, TypeError):
                    current_summary = {}

            # Handle products from form
            products = []
            product_count = 0
            while f'product_name_{product_count}' in request.form:
                product_name = request.form.get(f'product_name_{product_count}', '').strip()
                description = request.form.get(f'description_{product_count}', '').strip()
                product_id = request.form.get(f'product_id_{product_count}', '').strip()
                quantity_str = request.form.get(f'quantity_{product_count}', '0')
                unit_price_str = request.form.get(f'unit_price_{product_count}', '0.00')
                
                try:
                    quantity = int(quantity_str) if quantity_str else 0
                    unit_price = float(unit_price_str) if unit_price_str else 0.0
                    total_price = quantity * unit_price
                except ValueError:
                    quantity = 0
                    unit_price = 0.0
                    total_price = 0.0
                
                if product_name:  # Only add if product name exists
                    products.append({
                        'product_id': product_id,
                        'product_name': product_name,
                        'description': description,
                        'quantity': quantity,
                        'unit_price': unit_price,
                        'total_price': total_price
                    })
                product_count += 1

            # Reconstruct shipping_info from form fields
            shipping_info = {
                'shipping_full_name': request.form.get('shipping_full_name', current_shipping.get('shipping_full_name', '')),
                'shipping_email': request.form.get('shipping_email', current_shipping.get('shipping_email', '')),
                'shipping_address1': request.form.get('shipping_address1', current_shipping.get('shipping_address1', '')),
                'shipping_address2': request.form.get('shipping_address2', current_shipping.get('shipping_address2', '')),
                'shipping_city': request.form.get('shipping_city', current_shipping.get('shipping_city', '')),
                'shipping_state': request.form.get('shipping_state', current_shipping.get('shipping_state', '')),
                'shipping_zipcode': request.form.get('shipping_zipcode', current_shipping.get('shipping_zipcode', '')),
                'shipping_country': request.form.get('shipping_country', current_shipping.get('shipping_country', ''))
            }

            # Create order summary with products
            order_summary = {'products': products}

            # Sync top-level fields to shipping versions if provided
            new_email = request.form.get('email', order.get('email', ''))
            new_full_name = request.form.get('full_name', order.get('full_name', ''))
            if request.form.get('shipping_email'):
                new_email = request.form.get('shipping_email', '')
            if request.form.get('shipping_full_name'):
                new_full_name = request.form.get('shipping_full_name', '')

            # Calculate total from products or use form value
            calculated_total = sum(product['total_price'] for product in products)
            form_total = request.form.get('total', str(calculated_total))
            try:
                total = float(form_total)
            except ValueError:
                total = calculated_total

            orders_db[order_id] = {
                'order_summary': json.dumps(order_summary),
                'shipping_info': json.dumps(shipping_info),
                'total': total,
                'status': request.form.get('status', order.get('status', 'pending')),
                'email': new_email,
                'full_name': new_full_name,
                'shipping_address': request.form.get('shipping_address', order.get('shipping_address', ''))
            }
            return redirect(orders_url)
        
        return self.render('admin/edit_order.html', order=order, order_id=order_id, home_url=home_url, orders_url=orders_url)

    @expose('/delete/<int:order_id>')
    def delete(self, order_id):
        if order_id in orders_db:
            del orders_db[order_id]
        return redirect(url_for('orderview.index'))

admin.add_view(OrderView(name='Orders', endpoint='orderview'))

# Route for creating an order
@app.route('/process_checkout', methods=['POST'])
def process_checkout():
    global next_order_id
    try:
        data = request.json
        print("Data received from Django:", data)
        order_id = next_order_id
        shipping_info = data.get('shipping_info', {})
        
        # Handle cart_items data structure
        cart_items = data.get('cart_items', [])
        order_summary = {'products': []}
        
        # Convert cart_items to our products structure
        for item in cart_items:
            product = {
                'product_id': item.get('id', ''),
                'product_name': item.get('name', ''),
                'description': item.get('description', ''),
                'quantity': int(item.get('quantity', 1)),
                'unit_price': float(item.get('price', 0.0)),
                'total_price': int(item.get('quantity', 1)) * float(item.get('price', 0.0))
            }
            order_summary['products'].append(product)
        
        # If no cart_items, fall back to old structure
        if not cart_items:
            old_order_summary = data.get('order_summary', {'products': []})
            if isinstance(old_order_summary, dict) and 'products' in old_order_summary:
                order_summary = old_order_summary
            elif isinstance(old_order_summary, list):
                order_summary = {'products': old_order_summary}
        
        # Ensure each product has the required fields
        for product in order_summary['products']:
            if 'unit_price' not in product:
                product['unit_price'] = float(product.get('price', 0.0))
            if 'total_price' not in product:
                product['total_price'] = product.get('quantity', 0) * product.get('unit_price', 0.0)
        
        # Use total_amount if available, otherwise use total
        total_value = data.get('total_amount', data.get('total', 0.0))
        
        orders_db[order_id] = {
            'order_summary': json.dumps(order_summary),
            'shipping_info': json.dumps(shipping_info),
            'total': float(total_value),
            'status': data.get('status', 'pending'),
            'email': data.get('email', ''),
            'full_name': data.get('full_name', ''),
            'shipping_address': data.get('shipping_address', '')
        }
        next_order_id += 1
        response = {
            'status': 'success',
            'message': 'Payment processed and order created!',
            'order_id': order_id
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({'status': 'failed', 'message': f'An error occurred: {e}'})

# Debug route to inspect orders_db
@app.route('/debug_orders')
def debug_orders():
    return jsonify(orders_db)

# Other routes
@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = orders_db.get(order_id)
    if order:
        return jsonify({'status': 'success', 'order': order})
    return jsonify({'status': 'failed', 'message': 'Order not found'}), 404

@app.route('/orders/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    data = request.json
    order = orders_db.get(order_id)
    if not order:
        return jsonify({'status': 'failed', 'message': 'Order not found'}), 404
    for key, value in data.items():
        order[key] = value
    return jsonify({'status': 'success', 'message': 'Order updated successfully'})

@app.route('/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    if order_id in orders_db:
        del orders_db[order_id]
        return jsonify({'status': 'success', 'message': 'Order deleted successfully'})
    return jsonify({'status': 'failed', 'message': 'Order not found'}), 404

@app.route('/')
def index():
    return 'http://127.0.0.1:5000/admin'


if __name__ == '__main__':
    app.run(debug=True, port=5000)