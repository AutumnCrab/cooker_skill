// Part 2 - product list UI. Destructured props everywhere, plus an anonymous default export.

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

export default function ProductList({ products, onAdd, keyword }) {
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
