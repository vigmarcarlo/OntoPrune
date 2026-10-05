import { Order } from '../models/order';
import { IOrderRepository } from '../repositories/orderRepository';
import { PaymentService } from './paymentService';

export class CheckoutService {
    constructor(
        private orderRepo: IOrderRepository,
        private paymentService: PaymentService
    ) {}

    async processCheckout(order: Order, token: string): Promise<boolean> {
        if (!order || order.total <= 0) {
            return false;
        }

        const receipt = await this.paymentService.charge(order.total, token);
        if (!receipt.successful) {
            return false;
        }

        await this.orderRepo.save(order);
        return true;
    }
}
