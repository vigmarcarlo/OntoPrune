package com.shop.repository;

import com.shop.model.Order;
import java.util.Optional;

public interface OrderRepository {
    Order save(Order order);
    Optional<Order> findById(String id);
    void delete(Order order);
}
