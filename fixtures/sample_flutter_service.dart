// Sample Flutter/Dart Service Orchestrator
import 'package:flutter/foundation.dart';

class InventoryService {
  Future<bool> reservarStock(List<String> items) async {
    // Simulated network/db call
    return true;
  }
}

class BillingService {
  Future<String> emitirFactura(String orderId, double amount) async {
    return 'INV-$orderId';
  }
}

class OrderService {
  final InventoryService inventory;
  final BillingService billing;

  OrderService({required this.inventory, required this.billing});

  Future<bool> procesarOrden(String orderId, List<String> items, double amount) async {
    final reserved = await inventory.reservarStock(items);
    if (!reserved) {
      return false;
    }
    final invoice = await billing.emitirFactura(orderId, amount);
    if (kDebugMode) {
      print('Factura emitida: $invoice');
    }
    return true;
  }
}
