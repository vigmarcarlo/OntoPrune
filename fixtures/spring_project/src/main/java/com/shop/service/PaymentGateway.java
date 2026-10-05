package com.shop.service;

import com.shop.model.PaymentReceipt;

public interface PaymentGateway {
    PaymentReceipt charge(double amount, String paymentToken);
    void refund(String transactionId);
}
