package com.shop.service;

import com.shop.model.Order;
import com.shop.model.PaymentReceipt;
import com.shop.repository.OrderRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CheckoutService {

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private PaymentGateway paymentGateway;

    @Transactional
    public boolean processCheckout(Order order, String token) {
        if (order == null || order.getTotalAmount() <= 0) {
            return false;
        }

        PaymentReceipt receipt = paymentGateway.charge(order.getTotalAmount(), token);
        if (!receipt.isSuccessful()) {
            return false;
        }

        orderRepository.save(order);
        return true;
    }
}
