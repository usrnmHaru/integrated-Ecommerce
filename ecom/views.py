from django.shortcuts import render, redirect
from django.http import HttpResponse
import requests
import json
from django.conf import settings
from paypal.standard.forms import PayPalPaymentsForm
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

# Example view for checkout
def checkout(request):
    # Assuming cart_products, quantities, and totals are passed to the template
    cart_products = request.session.get('cart_products', [])  # Example: Fetch from session
    quantities = request.session.get('quantities', {})
    totals = request.session.get('totals', 0.0)
    shipping_form = ShippingForm(request.POST or None)  # Replace with your form

    if request.method == 'POST' and shipping_form.is_valid():
        shipping_info = shipping_form.save()
        request.session['shipping_info'] = {
            'shipping_full_name': shipping_info.shipping_full_name,
            'shipping_email': shipping_info.shipping_email,
            'shipping_address1': shipping_info.shipping_address1,
            'shipping_address2': shipping_info.shipping_address2,
            'shipping_city': shipping_info.shipping_city,
            'shipping_state': shipping_info.shipping_state,
            'shipping_zipcode': shipping_info.shipping_zipcode,
            'shipping_country': shipping_info.shipping_country,
        }
        return redirect('billing_info')

    return render(request, 'checkout.html', {
        'cart_products': cart_products,
        'quantities': quantities,
        'totals': totals,
        'shipping_form': shipping_form,
    })

# Example view for billing info
def billing_info(request):
    cart_products = request.session.get('cart_products', [])
    quantities = request.session.get('quantities', {})
    totals = request.session.get('totals', 0.0)
    shipping_info = request.session.get('shipping_info', {})
    billing_form = BillingForm(request.POST or None)  # Replace with your form

    # PayPal form setup
    paypal_dict = {
        "business": settings.PAYPAL_RECEIVER_EMAIL,
        "amount": str(totals),
        "item_name": "Order",
        "invoice": f"order_{int(totals * 100)}_{request.session.session_key}",
        "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
        "return_url": request.build_absolute_uri(reverse('payment_success')),
        "cancel_return": request.build_absolute_uri(reverse('payment_failed')),
        "currency_code": "USD",
    }
    paypal_form = PayPalPaymentsForm(initial=paypal_dict)

    if request.method == 'POST' and billing_form.is_valid():
        # Save billing info and proceed to payment
        billing_info = billing_form.save()
        request.session['billing_info'] = billing_form.cleaned_data
        return render(request, 'process_order.html', {
            'cart_products': cart_products,
            'quantities': quantities,
            'totals': totals,
            'shipping_info': shipping_info,
            'billing_form': billing_form,
        })

    return render(request, 'billing_info.html', {
        'cart_products': cart_products,
        'quantities': quantities,
        'totals': totals,
        'shipping_info': shipping_info,
        'paypal_form': paypal_form,
        'billing_form': billing_form,
    })

# Handle PayPal IPN and send to Flask
@csrf_exempt
def process_order(request):
    if request.method == 'POST':
        cart_products = request.session.get('cart_products', [])
        quantities = request.session.get('quantities', {})
        totals = request.session.get('totals', 0.0)
        shipping_info = request.session.get('shipping_info', {})

        # Format items for Flask
        items = [
            {
                'product': product['name'],
                'quantity': quantities.get(str(product['id']), 1),
                'price': product['sale_price'] if product.get('is_sale') else product['price']
            }
            for product in cart_products
        ]

        # Send order data to Flask
        flask_url = 'http://127.0.0.1:5000/process_checkout'
        order_data = {
            'items': json.dumps(items),  # Serialize items as JSON string
            'total': float(totals),
            'status': 'pending',
            'email': shipping_info.get('shipping_email', ''),
            'full_name': shipping_info.get('shipping_full_name', ''),
            'shipping_address': f"{shipping_info.get('shipping_address1', '')}, {shipping_info.get('shipping_address2', '')}, {shipping_info.get('shipping_city', '')}, {shipping_info.get('shipping_state', '')}, {shipping_info.get('shipping_zipcode', '')}, {shipping_info.get('shipping_country', '')}"
        }

        try:
            response = requests.post(flask_url, json=order_data)
            response_data = response.json()
            if response_data.get('status') == 'success':
                # Clear cart and session data
                request.session['cart_products'] = []
                request.session['quantities'] = {}
                request.session['totals'] = 0.0
                request.session['shipping_info'] = {}
                return redirect('payment_success')
            else:
                return redirect('payment_failed')
        except Exception as e:
            print(f"Error sending to Flask: {e}")
            return redirect('payment_failed')

    return redirect('payment_failed')

def payment_success(request):
    return render(request, 'payment_success.html')

def payment_failed(request):
    return render(request, 'payment_failed.html')