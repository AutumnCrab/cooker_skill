// Merged shop page - cart + list + checkout.
// The two money implementations were unified on part 1, so VAT_RATE is gone and
// orderTotal now goes through subtotal/shippingFee. Cooker reports exactly that.
import { useState } from "react";

/* ---- part 1: cart math ---- */
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

/* ---- part 3: coupons, now reusing part 1's math ---- */
export const COUPON_CODES = {
  WELCOME: 0.1,
  VIP: 0.2
};

export function couponDiscount(amount, code) {
  const rate = COUPON_CODES[code];
  if (!rate) return 0;
  return Math.round(amount * rate);
}

export function orderTotal(items, code) {
  const base = subtotal(items);
  const discount = couponDiscount(base, code);
  const taxed = Math.round((base - discount) * (1 + TAX_RATE));
  return taxed + shippingFee(base - discount);
}

export function validateOrder(items, address) {
  const errors = [];
  if (items.length === 0) errors.push("cart is empty");
  if (!address || address.trim().length < 5) errors.push("address must be at least 5 characters");
  return errors;
}

/* ---- part 2: list UI ---- */
export const CURRENCY = "USD";

export function formatPrice(value) {
  return "$" + (value / 100).toFixed(2);
}

export function stockLabel(stock) {
  if (stock <= 0) return "sold out";
  if (stock < 5) return "almost gone";
  return "in stock";
}

export function ProductRow({ product, onAdd }) {
  const soldOut = product.stock <= 0;
  return (
    <li className={soldOut ? "row sold-out" : "row"}>
      <span className="name">{product.name}</span>
      <span className="price">{formatPrice(product.price)}</span>
      <span className="stock">{stockLabel(product.stock)}</span>
      <button disabled={soldOut} onClick={() => onAdd(product)}>
        add
      </button>
    </li>
  );
}

export function ProductList({ products, onAdd, keyword }) {
  const visible = products.filter((p) =>
    p.name.toLowerCase().includes(keyword.trim().toLowerCase())
  );
  if (visible.length === 0) {
    return <p className="empty">no matches</p>;
  }
  return (
    <ul className="product-list">
      {visible.map((product) => (
        <ProductRow key={product.id} product={product} onAdd={onAdd} />
      ))}
    </ul>
  );
}

/* ---- part 3: checkout UI ---- */
export function Checkout({ items, coupon, address, onSubmit }) {
  const errors = validateOrder(items, address);
  const total = orderTotal(items, coupon);
  return (
    <section className="checkout">
      <h2>order summary</h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            {item.name} x {item.qty}
          </li>
        ))}
      </ul>
      <p className="total">total {formatPrice(total)}</p>
      {errors.length > 0 && (
        <ul className="errors">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
      <button disabled={errors.length > 0} onClick={() => onSubmit(total)}>
        pay
      </button>
    </section>
  );
}

/* ---- the seam ---- */
export default function ShopPage({ products }) {
  const cart = useCart([]);
  const [keyword, setKeyword] = useState("");
  const [coupon, setCoupon] = useState("");
  const [address, setAddress] = useState("");

  return (
    <main className="shop">
      <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="search" />
      <ProductList products={products} onAdd={cart.add} keyword={keyword} />
      <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="coupon" />
      <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="address" />
      <Checkout
        items={cart.items}
        coupon={coupon}
        address={address}
        onSubmit={(total) => alert(formatPrice(total))}
      />
    </main>
  );
}
