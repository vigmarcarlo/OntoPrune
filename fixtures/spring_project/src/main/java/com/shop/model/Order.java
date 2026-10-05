package com.shop.model;

public class Order {
    private String id;
    private double totalAmount;
    private String status;

    public Order(String id, double totalAmount, String status) {
        this.id = id;
        this.totalAmount = totalAmount;
        this.status = status;
    }

    public String getId() {
        return id;
    }

    public double getTotalAmount() {
        return totalAmount;
    }

    public String getStatus() {
        return status;
    }
}
