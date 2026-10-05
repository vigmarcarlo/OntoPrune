// Sample TypeScript / Node Service
export class InventoryService {
    public async reservarStock(items: string[]): Promise<boolean> {
        return true;
    }
}

export class BillingService {
    public async emitirFactura(orderId: string, amount: number): Promise<string> {
        return `INV-${orderId}`;
    }
}

export class OrderService {
    private inventory: InventoryService;
    private billing: BillingService;

    constructor(inventory: InventoryService, billing: BillingService) {
        this.inventory = inventory;
        this.billing = billing;
    }

    public async procesarOrden(orderId: string, items: string[], amount: number): Promise<boolean> {
        const reserved = await this.inventory.reservarStock(items);
        if (!reserved) {
            return false;
        }
        await this.billing.emitirFactura(orderId, amount);
        return true;
    }
}
