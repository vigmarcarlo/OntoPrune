import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

// --- Domain Models ---
class OrderItem {
  final String productId;
  final int quantity;
  final double unitPrice;

  OrderItem({
    required this.productId,
    required this.quantity,
    required this.unitPrice,
  });

  double get subtotal => quantity * unitPrice;
}

enum OrderStatus { pending, processing, completed, failed }

class Order {
  final String id;
  final List<OrderItem> items;
  final double totalAmount;
  OrderStatus status;

  Order({
    required this.id,
    required this.items,
    required this.totalAmount,
    this.status = OrderStatus.pending,
  });
}

// --- Repositories & External Services ---
abstract class IOrderRepository {
  Future<Order> createOrder(Order order);
  Future<void> updateStatus(String orderId, OrderStatus status);
  Stream<OrderStatus> watchOrderStatus(String orderId);
}

class InventoryService {
  Future<bool> checkAndReserve(List<OrderItem> items) async {
    await Future.delayed(const Duration(milliseconds: 50));
    return items.every((i) => i.quantity > 0);
  }

  Future<void> releaseReservation(List<OrderItem> items) async {
    await Future.delayed(const Duration(milliseconds: 20));
  }
}

class PaymentGateway {
  Future<String> chargeCard({
    required String customerId,
    required double amount,
    required String currency,
  }) async {
    if (amount <= 0) throw ArgumentError('Amount must be positive');
    return 'txn_${DateTime.now().millisecondsSinceEpoch}';
  }
}

class AnalyticsTracker {
  void logEvent(String name, Map<String, dynamic> parameters) {
    if (kDebugMode) {
      print('Analytics: $name => $parameters');
    }
  }
}

// --- State Management: ChangeNotifier Controller ---
class CheckoutController extends ChangeNotifier {
  final IOrderRepository _orderRepo;
  final InventoryService _inventory;
  final PaymentGateway _paymentGateway;
  final AnalyticsTracker _analytics;

  bool _isProcessing = false;
  String? _errorMessage;

  CheckoutController({
    required IOrderRepository orderRepo,
    required InventoryService inventory,
    required PaymentGateway paymentGateway,
    required AnalyticsTracker analytics,
  })  : _orderRepo = orderRepo,
        _inventory = inventory,
        _paymentGateway = paymentGateway,
        _analytics = analytics;

  bool get isProcessing => _isProcessing;
  String? get errorMessage => _errorMessage;

  @override
  void dispose() {
    _analytics.logEvent('checkout_screen_disposed', {});
    super.dispose();
  }

  Future<bool> executeCheckout(String customerId, Order order) async {
    _isProcessing = true;
    _errorMessage = null;
    notifyListeners();

    _analytics.logEvent('checkout_started', {'order_id': order.id, 'amount': order.totalAmount});

    try {
      final stockReserved = await _inventory.checkAndReserve(order.items);
      if (!stockReserved) {
        _errorMessage = 'Stock not available';
        await _orderRepo.updateStatus(order.id, OrderStatus.failed);
        return false;
      }

      final transactionId = await _paymentGateway.chargeCard(
        customerId: customerId,
        amount: order.totalAmount,
        currency: 'USD',
      );

      order.status = OrderStatus.completed;
      await _orderRepo.createOrder(order);
      await _orderRepo.updateStatus(order.id, OrderStatus.completed);

      _analytics.logEvent('checkout_success', {
        'order_id': order.id,
        'txn': transactionId,
      });

      return true;
    } catch (e, stack) {
      _errorMessage = e.toString();
      await _inventory.releaseReservation(order.items);
      await _orderRepo.updateStatus(order.id, OrderStatus.failed);
      _analytics.logEvent('checkout_error', {'error': e.toString(), 'stack': stack.toString()});
      return false;
    } finally {
      _isProcessing = false;
      notifyListeners();
    }
  }
}

// --- Flutter UI: StatefulWidget Widget Tree ---
class CheckoutScreen extends StatefulWidget {
  final String customerId;
  final Order currentOrder;

  const CheckoutScreen({
    super.key,
    required this.customerId,
    required this.currentOrder,
  });

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  late final CheckoutController _controller;

  @override
  void initState() {
    super.initState();
    // In real app, dependencies are injected via Provider/GetIt
    _controller = CheckoutController(
      orderRepo: _StubOrderRepository(),
      inventory: InventoryService(),
      paymentGateway: PaymentGateway(),
      analytics: AnalyticsTracker(),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: ListenableBuilder(
        listenable: _controller,
        builder: (context, child) {
          if (_controller.isProcessing) {
            return const Center(child: CircularProgressIndicator());
          }
          return Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Order Total: \$${widget.currentOrder.totalAmount.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                if (_controller.errorMessage != null)
                  Text(
                    _controller.errorMessage!,
                    style: const TextStyle(color: Colors.red),
                  ),
                const Spacer(),
                ElevatedButton(
                  onPressed: () async {
                    final success = await _controller.executeCheckout(
                      widget.customerId,
                      widget.currentOrder,
                    );
                    if (success && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Order completed!')),
                      );
                    }
                  },
                  child: const Text('Confirm Order'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _StubOrderRepository implements IOrderRepository {
  @override
  Future<Order> createOrder(Order order) async => order;

  @override
  Future<void> updateStatus(String orderId, OrderStatus status) async {}

  @override
  Stream<OrderStatus> watchOrderStatus(String orderId) => const Stream.empty();
}
