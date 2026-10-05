package com.shop.model;

public class PaymentReceipt {
    private String transactionId;
    private boolean successful;

    public PaymentReceipt(String transactionId, boolean successful) {
        this.transactionId = transactionId;
        this.successful = successful;
    }

    public String getTransactionId() {
        return transactionId;
    }

    public boolean isSuccessful() {
        return successful;
    }
}
