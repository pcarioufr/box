import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Excalidraw, convertToExcalidrawElements } from '@excalidraw/excalidraw'
import type { ExcalidrawImperativeAPI } from '@excalidraw/excalidraw/types/types'
import type { ExcalidrawElement } from '@excalidraw/excalidraw/types/element/types'

// Server adds metadata fields that Excalidraw doesn't understand — strip them
const SERVER_FIELDS = ['createdAt', 'updatedAt', 'version', 'syncedAt', 'source', 'syncTimestamp']

function stripServerFields(element: any): Partial<ExcalidrawElement> {
  const clean = { ...element }
  for (const key of SERVER_FIELDS) delete clean[key]
  return clean
}

/**
 * Prepare elements for Excalidraw.
 * Full elements (from browser sync) have a `seed` — pass them directly to preserve bindings.
 * Skeleton elements (from API, with `label` sugar) need convertToExcalidrawElements().
 */
function prepareElements(elements: any[]): ExcalidrawElement[] {
  const cleaned = elements.map(stripServerFields)
  if (cleaned.length > 0 && typeof cleaned[0].seed === 'number') {
    return cleaned as ExcalidrawElement[]
  }
  return convertToExcalidrawElements(cleaned, { regenerateIds: false }) as ExcalidrawElement[]
}

function App() {
  const [initialElements, setInitialElements] = useState<ExcalidrawElement[] | null>(null)
  const excalidrawAPIRef = useRef<ExcalidrawImperativeAPI | null>(null)
  const messageQueueRef = useRef<any[]>([])
  const isRemoteUpdateRef = useRef(false)

  // Fetch initial elements before rendering Excalidraw
  useEffect(() => {
    fetch('/api/elements')
      .then(res => res.json())
      .then(data => {
        if (data.success && data.elements && data.elements.length > 0) {
          console.log('[Box] Pre-fetched elements:', data.elements.length)
          setInitialElements(prepareElements(data.elements))
        } else {
          setInitialElements([])
        }
      })
      .catch(() => setInitialElements([]))
  }, [])

  // Guard: mark scene updates as remote so onChange doesn't echo them back
  const applyRemoteUpdate = useCallback((fn: () => void) => {
    isRemoteUpdateRef.current = true
    fn()
    setTimeout(() => { isRemoteUpdateRef.current = false }, 100)
  }, [])

  // Fetch elements from REST API (for subsequent updates)
  const fetchAndLoadElements = useCallback(async () => {
    const api = excalidrawAPIRef.current
    if (!api) return

    try {
      const response = await fetch('/api/elements')
      const data = await response.json()
      if (data.success && data.elements) {
        console.log('[Box] Fetched elements:', data.elements.length)
        applyRemoteUpdate(() => {
          api.updateScene({ elements: prepareElements(data.elements) })
        })
      }
    } catch (e) {
      console.error('[Box] Failed to fetch elements:', e)
    }
  }, [applyRemoteUpdate])

  // Process a single WebSocket message
  const processMessage = useCallback((msg: any) => {
    const api = excalidrawAPIRef.current
    if (!api) return false

    console.log('[Box] Processing message:', msg.type)

    switch (msg.type) {
      case 'initial_elements':
        // Skip - we already loaded via initialData
        break

      case 'element_created':
      case 'elements_batch_created': {
        const incoming = msg.elements || (msg.element ? [msg.element] : [])
        if (incoming.length > 0) {
          const cleaned = incoming.map(stripServerFields)
          const converted = convertToExcalidrawElements(cleaned, { regenerateIds: false })
          applyRemoteUpdate(() => {
            api.updateScene({ elements: [...api.getSceneElements(), ...converted] })
          })
        }
        break
      }

      case 'element_updated':
        console.log('[Box] Element updated, refreshing all elements')
        fetchAndLoadElements()
        break

      case 'element_deleted':
        if (msg.elementId) {
          applyRemoteUpdate(() => {
            const filtered = api.getSceneElements().filter(el => el.id !== msg.elementId)
            api.updateScene({ elements: filtered })
          })
        }
        break

      case 'clear':
        applyRemoteUpdate(() => api.updateScene({ elements: [] }))
        break

      case 'refresh':
        fetchAndLoadElements()
        break
    }
    return true
  }, [fetchAndLoadElements])

  // Handle Excalidraw API ready
  const handleAPIReady = useCallback((api: ExcalidrawImperativeAPI) => {
    console.log('[Box] Excalidraw API ready')
    excalidrawAPIRef.current = api

    // Process any queued messages (skip initial_elements since we used initialData)
    while (messageQueueRef.current.length > 0) {
      const msg = messageQueueRef.current.shift()
      processMessage(msg)
    }
  }, [processMessage])

  // Connect to WebSocket (receive-only — no user edits sent to server)
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}`)

    ws.onopen = () => {
      console.log('[Box] WebSocket connected')
    }

    ws.onclose = () => {
      console.log('[Box] WebSocket disconnected')
      setTimeout(() => { window.location.reload() }, 3000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (!excalidrawAPIRef.current) {
          console.log('[Box] API not ready, queuing message:', msg.type)
          messageQueueRef.current.push(msg)
          return
        }

        processMessage(msg)
      } catch (e) {
        console.error('[Box] Failed to parse message:', e)
      }
    }

    return () => ws.close()
  }, [processMessage])

  // Don't render Excalidraw until initial elements are fetched
  if (initialElements === null) {
    return null
  }

  return (
    <div style={{ height: '100vh', width: '100vw' }}>
      <Excalidraw
        excalidrawAPI={handleAPIReady}
        initialData={{
          elements: initialElements,
          appState: { viewBackgroundColor: '#ffffff' }
        }}
      />
    </div>
  )
}

export default App
