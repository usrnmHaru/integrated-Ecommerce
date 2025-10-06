from django.shortcuts import render, redirect
from cart.cart import Cart
from payment.forms import ShippingForm, PaymentForm
from payment.models import ShippingAddress, Order, OrderItem
from django.contrib.auth.models import User
from django.contrib import messages
from store.models import Product, Profile
import datetime
import requests
import json
from django.urls import reverse
from paypal.standard.forms import PayPalPaymentsForm
from django.conf import settings
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def orders(request, pk):
    if request.user.is_authenticated and request.user.is_superuser:
        order = Order.objects.get(id=pk)
        items = OrderItem.objects.filter(order=pk)

        if request.POST:
            status = request.POST['shipping_status']
            if status == "true":
                order = Order.objects.filter(id=pk)
                now = datetime.datetime.now()
                order.update(shipped=True, date_shipped=now)
                # Update Flask API
                try:
                    requests.put(f'http://127.0.0.1:5000/orders/{pk}', json={'status': 'shipped'})
                except requests.exceptions.RequestException as e:
                    messages.error(request, f"Failed to update Flask API: {e}")
            else:
                order = Order.objects.filter(id=pk)
                order.update(shipped=False)
                try:
                    requests.put(f'http://127.0.0.1:5000/orders/{pk}', json={'status': 'pending'})
                except requests.exceptions.RequestException as e:
                    messages.error(request, f"Failed to update Flask API: {e}")
            messages.success(request, "Shipping Status Updated")
            return redirect('home')

        return render(request, 'payment/orders.html', {"order": order, "items": items})
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def not_shipped_dash(request):
    if request.user.is_authenticated and request.user.is_superuser:
        orders = Order.objects.filter(shipped=False)
        if request.POST:
            status = request.POST.get('shipping_status')
            num = request.POST.get('num')
            if status and num:
                order = Order.objects.filter(id=num)
                if order.exists():
                    now = datetime.datetime.now()
                    order.update(shipped=True, date_shipped=now)
                    # Update Flask API
                    try:
                        requests.put(f'http://127.0.0.1:5000/orders/{num}', json={'status': 'shipped'})
                    except requests.exceptions.RequestException as e:
                        messages.error(request, f"Failed to update Flask API: {e}")
                    messages.success(request, "Shipping Status Updated")
                else:
                    messages.error(request, "Order not found")
            else:
                messages.error(request, "Invalid form data")
            return redirect('not_shipped_dash')  # Redirect to same dashboard
        return render(request, "payment/not_shipped_dash.html", {"orders": orders})
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def shipped_dash(request):
    if request.user.is_authenticated and request.user.is_superuser:
        orders = Order.objects.filter(shipped=True)
        if request.POST:
            status = request.POST.get('shipping_status')
            num = request.POST.get('num')
            if status and num:
                order = Order.objects.filter(id=num)
                if order.exists():
                    order.update(shipped=False)
                    # Update Flask API
                    try:
                        requests.put(f'http://127.0.0.1:5000/orders/{num}', json={'status': 'pending'})
                    except requests.exceptions.RequestException as e:
                        messages.error(request, f"Failed to update Flask API: {e}")
                    messages.success(request, "Shipping Status Updated")
                else:
                    messages.error(request, "Order not found")
            else:
                messages.error(request, "Invalid form data")
            return redirect('shipped_dash')  # Redirect to same dashboard
        return render(request, "payment/shipped_dash.html", {"orders": orders})
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def process_order(request):
    if request.POST:
        cart = Cart(request)
        cart_products = cart.get_prods
        quantities = cart.get_quants
        totals = cart.cart_total()

        payment_form = PaymentForm(request.POST or None)
        my_shipping = request.session.get('my_shipping')

        full_name = my_shipping['shipping_full_name']
        email = my_shipping['shipping_email']
        shipping_address = f"{my_shipping['shipping_address1']}\n{my_shipping['shipping_address2']}\n{my_shipping['shipping_city']}\n{my_shipping['shipping_state']}\n{my_shipping['shipping_zipcode']}\n{my_shipping['shipping_country']}"
        amount_paid = totals

        if request.user.is_authenticated:
            user = request.user
            create_order = Order(user=user, full_name=full_name, email=email, shipping_address=shipping_address,
                                 amount_paid=amount_paid)
            create_order.save()
            order_id = create_order.pk
            for product in cart_products():
                product_id = product.id
                price = product.sale_price if product.is_sale else product.price
                for key, value in quantities().items():
                    if int(key) == product.id:
                        create_order_item = OrderItem(order_id=order_id, product_id=product_id, user=user,
                                                      quantity=value, price=price)
                        create_order_item.save()
            for key in list(request.session.keys()):
                if key == "session_key":
                    del request.session[key]
            current_user = Profile.objects.filter(user__id=request.user.id)
            current_user.update(old_cart="")
            messages.success(request, "Order Placed!")
            return redirect('home')
        else:
            create_order = Order(full_name=full_name, email=email, shipping_address=shipping_address,
                                 amount_paid=amount_paid)
            create_order.save()
            order_id = create_order.pk
            for product in cart_products():
                product_id = product.id
                price = product.sale_price if product.is_sale else product.price
                for key, value in quantities().items():
                    if int(key) == product.id:
                        create_order_item = OrderItem(order_id=order_id, product_id=product_id, quantity=value,
                                                      price=price)
                        create_order_item.save()
            for key in list(request.session.keys()):
                if key == "session_key":
                    del request.session[key]
            messages.success(request, "Order Placed!")
            return redirect('home')
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def billing_info(request):
    if request.POST:
        cart = Cart(request)
        cart_products = cart.get_prods
        quantities = cart.get_quants
        totals = cart.cart_total()
        my_shipping = request.POST
        request.session['my_shipping'] = my_shipping
        total_amount_str = str(totals)
        data_to_send = {
            'shipping_info': dict(my_shipping.items()),
            'cart_items': [
                {
                    'id': str(p.id),
                    'name': p.name,
                    'price': str(p.sale_price if p.is_sale else p.price),
                    'quantity': quantities().get(str(p.id))
                } for p in cart_products()
            ],
            'total_amount': total_amount_str
        }
        api_url = 'http://127.0.0.1:5000/process_checkout'
        try:
            response = requests.post(api_url, json=data_to_send)
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    full_name = my_shipping['shipping_full_name']
                    email = my_shipping['shipping_email']
                    shipping_address = f"{my_shipping['shipping_address1']}\n{my_shipping['shipping_address2']}\n{my_shipping['shipping_city']}\n{my_shipping['shipping_state']}\n{my_shipping['shipping_zipcode']}\n{my_shipping['shipping_country']}"
                    amount_paid = totals
                    if request.user.is_authenticated:
                        user = request.user
                        create_order = Order(user=user, full_name=full_name, email=email, shipping_address=shipping_address,
                                             amount_paid=amount_paid)
                        create_order.save()
                        order_id = create_order.pk
                        for product in cart_products():
                            product_id = product.id
                            price = product.sale_price if product.is_sale else product.price
                            for key, value in quantities().items():
                                if int(key) == product.id:
                                    create_order_item = OrderItem(order_id=order_id, product_id=product_id, user=user,
                                                                  quantity=value, price=price)
                                    create_order_item.save()
                    else:
                        create_order = Order(full_name=full_name, email=email, shipping_address=shipping_address,
                                             amount_paid=amount_paid)
                        create_order.save()
                        order_id = create_order.pk
                        for product in cart_products():
                            product_id = product.id
                            price = product.sale_price if product.is_sale else product.price
                            for key, value in quantities().items():
                                if int(key) == product.id:
                                    create_order_item = OrderItem(order_id=order_id, product_id=product_id, quantity=value,
                                                                  price=price)
                                    create_order_item.save()
                    for key in list(request.session.keys()):
                        if key == "session_key":
                            del request.session[key]
                    if request.user.is_authenticated:
                        current_user = Profile.objects.filter(user__id=request.user.id)
                        current_user.update(old_cart="")
                    messages.success(request, "Payment was successful and order saved!")
                    return redirect('payment_success')
                else:
                    messages.error(request, f"Payment failed: {result.get('message', 'An error occurred.')}")
                    return redirect('payment_failed')
            else:
                messages.error(request, "Error communicating with the payment service.")
                return redirect('payment_failed')
        except requests.exceptions.RequestException as e:
            messages.error(request, f"Could not connect to the payment service. Please try again later. Error: {e}")
            return redirect('payment_failed')
    else:
        messages.success(request, "Access Denied")
        return redirect('home')

def checkout(request):
    cart = Cart(request)
    cart_products = cart.get_prods
    quantities = cart.get_quants
    totals = cart.cart_total()
    if request.user.is_authenticated:
        shipping_user = ShippingAddress.objects.get(user__id=request.user.id)
        shipping_form = ShippingForm(request.POST or None, instance=shipping_user)
        return render(request, "payment/checkout.html",
                      {"cart_products": cart_products, "quantities": quantities, "totals": totals,
                       "shipping_form": shipping_form})
    else:
        shipping_form = ShippingForm(request.POST or None)
        return render(request, "payment/checkout.html",
                      {"cart_products": cart_products, "quantities": quantities, "totals": totals,
                       "shipping_form": shipping_form})

def payment_success(request):
    return render(request, "payment/payment_success.html", {})

def payment_failed(request):
    return render(request, "payment/payment_failed.html", {})

@csrf_exempt
def update_order_status(request, pk):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        status = data.get('status')
        if status not in ['shipped', 'pending']:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        try:
            order = Order.objects.get(id=pk)
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
        if status == 'shipped':
            now = datetime.datetime.now()
            order.shipped = True
            order.date_shipped = now
        else:
            order.shipped = False
            order.date_shipped = None  # Reset date_shipped when unshipped
        order.save()
        return JsonResponse({'status': 'success', 'message': 'Shipping Status Updated'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def delete_order(request, pk):
    if request.method == 'DELETE':
        try:
            order = Order.objects.get(id=pk)
            order.delete()
            return JsonResponse({'status': 'success', 'message': 'Order deleted successfully'})
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Failed to delete order: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)