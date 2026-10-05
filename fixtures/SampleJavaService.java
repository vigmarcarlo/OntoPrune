// Sample Java Spring Boot Service
package com.empresa.service;

import java.util.List;

class InventoryService {
    public boolean reservarStock(List<String> items) {
        return true;
    }
}

class BillingService {
    public String emitirFactura(String orderId, double amount) {
        return "INV-" + orderId;
    }
}

public class OrderService {
    private InventoryService inventory;
    private BillingService billing;

    public OrderService(InventoryService inventory, BillingService billing) {
        this.inventory = inventory;
        this.billing = billing;
    }

    public boolean procesarOrden(String orderId, List<String> items, double amount) {
        boolean reserved = inventory.reservarStock(items);
        if (!reserved) {
            return false;
        }
        billing.emitirFactura(orderId, amount);
        return true;
    }
}
