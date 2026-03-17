# @nexra/sdk

TypeScript SDK for Nexra.

## Install

```bash
npm install @nexra/sdk
```

## Build

```bash
npm run build
```

## Usage

```ts
import { NexraClient } from '@nexra/sdk';

const client = new NexraClient({
  apiKey: process.env.NEXRA_API_KEY!,
  baseUrl: 'https://api.usenexra.com/v1',
});
```
