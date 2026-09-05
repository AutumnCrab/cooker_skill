// Part 1 - cart state and money math.
import { useState } from "react";

export const TAX_RATE = 0.1;
export const FREE_SHIPPING_OVER = 50000;
export const SHIPPING_FEE = 3000;

export function addItem(items, product) {
  const existing = items.find((item) => item.id === product.id);
  if (existing) {
    return items.map((item) =>
      item.id === product.id ? { ...item, qty: item.qty + 1 } : item
    );
  }
  return items.concat({ ...product, qty: 1 });
}

export function changeQty(items, id, delta) {
  return items
    .map((item) => (item.id === id ? { ...item, qty: item.qty + delta } : item))
    .filter((item) => item.qty > 0);
}

export function subtotal(items) {
  return items.reduce((sum, item) => sum + item.price * item.qty, 0);
}

export function shippingFee(amount) {
  return amount >= FREE_SHIPPING_OVER ? 0 : SHIPPING_FEE;
}

export function totalWithTax(items) {
  const base = subtotal(items);
  return Math.round(base * (1 + TAX_RATE)) + shippingFee(base);
}

export function useCart(initial = []) {
  const [items, setItems] = useState(initial);
  return {
    items,
    add: (product) => setItems((current) => addItem(current, product)),
    change: (id, delta) => setItems((current) => changeQty(current, id, delta)),
    total: totalWithTax(items)
  };
}
