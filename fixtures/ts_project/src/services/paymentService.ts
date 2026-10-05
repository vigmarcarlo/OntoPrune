import { PaymentReceipt } from '../models/order';

export class PaymentService {
    async charge(amount: number, token: string): Promise<PaymentReceipt> {
        return {
            transactionId: "tx_ts_123",
            successful: true,
        };
    }

    async refund(transactionId: string): Promise<void> {
        // refund
    }
}
