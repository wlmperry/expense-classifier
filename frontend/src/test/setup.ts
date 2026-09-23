import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Testing Library only unmounts rendered components automatically when Vitest
// `globals` is enabled. It is not, so without this every test's render would
// stay in the DOM and leak into the next test's queries.
afterEach(() => {
  cleanup()
})
