// Part 3 - checkout. Written without knowing part 1 exists, so it re-implements the
// money math with its own tax constant. That duplication is the merge hazard.

export const VAT_RATE = 0.1;
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
  const base = items.reduce((sum, item) => sum + item.price * item.qty, 0);
  const discount = couponDiscount(base, code);
  return Math.round((base - discount) * (1 + VAT_RATE));
}

export function validateOrder(items, address) {
  const errors = [];
  if (items.length === 0) errors.push("cart is empty");
  if (!address || address.trim().length < 5) errors.push("address must be at least 5 characters");
  return errors;
}

export default function Checkout({ items, coupon, address, onSubmit }) {
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
      <p className="total">total {total}</p>
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
