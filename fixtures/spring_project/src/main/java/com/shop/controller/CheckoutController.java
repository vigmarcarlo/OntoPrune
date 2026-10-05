package com.shop.controller;

import com.shop.model.Order;
import com.shop.service.CheckoutService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CheckoutController {

    @Autowired
    private CheckoutService checkoutService;

    @PostMapping("/checkout")
    public boolean checkout(@RequestBody Order order) {
        return checkoutService.processCheckout(order, "tok_12345");
    }
}
