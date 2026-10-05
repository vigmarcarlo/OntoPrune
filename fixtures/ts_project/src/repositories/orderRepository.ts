import { Order } from '../models/order';

export interface IOrderRepository {
    save(order: Order): Promise<Order>;
    findById(id: string): Promise<Order | null>;
    delete(id: string): Promise<void>;
}

export class OrderRepository implements IOrderRepository {
    async save(order: Order): Promise<Order> {
        return order;
    }

    async findById(id: string): Promise<Order | null> {
        return null;
    }

    async delete(id: string): Promise<void> {
        // deleted
    }
}
