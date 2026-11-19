import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

const product = {id: 1, name: 'Miniature', stock: 2, price: '100.00', description: 'Beginner'};
const payload = {preferences: 'I want miniatures', budget: '150', max_items: 3, products: [product]};
function request(body = payload, key = 'secret') {
  return new Request('https://example.test/recommendations', {method: 'POST', headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + key}, body: JSON.stringify(body)});
}
function env(items) {return {SERVICE_API_KEY: 'secret', AI: {run: async () => ({response: JSON.stringify({items})})}};}
test('public health endpoint', async () => {
  const response = await worker.fetch(new Request('https://example.test/health'), {});
  assert.equal(response.status, 200);
  assert.equal((await response.json()).status, 'ok');
});
test('unauthorized calls are rejected before inference', async () => {
  const response = await worker.fetch(request(payload, 'wrong'), env([]));
  assert.equal(response.status, 401);
});
test('invalid payload rejected', async () => {
  assert.equal((await worker.fetch(request({...payload, budget: -1}), env([]))).status, 400);
  assert.equal((await worker.fetch(request({...payload, products: [product, product]}), env([]))).status, 400);
});
test('only existing unique affordable items with stock survive', async () => {
  const response = await worker.fetch(request(), env([
    {product_id: 999, quantity: 1, reason: 'invalid'}, {product_id: 1, quantity: 3, reason: 'overstock'},
    {product_id: 1, quantity: 2, reason: 'over budget'}, {product_id: 1, quantity: 1, reason: 'valid'},
    {product_id: 1, quantity: 1, reason: 'duplicate'}]));
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).items, [{product_id: 1, quantity: 1, reason: 'valid'}]);
});
test('empty candidates avoid model invocation', async () => {
  const response = await worker.fetch(request({...payload, products: []}), {SERVICE_API_KEY: 'secret'});
  assert.deepEqual((await response.json()).items, []);
});
test('model failures return 502', async () => {
  const response = await worker.fetch(request(), {SERVICE_API_KEY: 'secret', AI: {run: async () => {throw Error('unavailable');}}});
  assert.equal(response.status, 502);
});
test('oversized body is rejected', async () => {
  const response = await worker.fetch(request({...payload, padding: 'a'.repeat(170000)}), env([]));
  assert.equal(response.status, 413);
});
