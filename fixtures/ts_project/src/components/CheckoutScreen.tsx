import * as React from 'react';
import { Order } from '../models/order';
import { CheckoutService } from '../services/checkoutService';

interface Props {
    controller: CheckoutService;
    order: Order;
}

export const CheckoutScreen: React.FC<Props> = ({ controller, order }) => {
    const [loading, setLoading] = React.useState(false);

    const handlePay = async () => {
        setLoading(true);
        await controller.processCheckout(order, "tok_web_99");
        setLoading(false);
    };

    return (
        <div>
            <h1>Checkout</h1>
            <button onClick={handlePay} disabled={loading}>
                Pay Now
            </button>
        </div>
    );
};
