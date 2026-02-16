import { ref, onUnmounted } from 'vue'

export interface DragState {
  isDragging: boolean
  draggedItem: unknown | null
  dragType: string | null
  startX: number
  startY: number
  currentX: number
  currentY: number
  offsetX: number
  offsetY: number
}

export interface UseDragAndDropOptions {
  onDragStart?: (item: unknown, type: string) => void
  onDragMove?: (x: number, y: number) => void
  onDragEnd?: (item: unknown, type: string, x: number, y: number) => void
  onDrop?: (item: unknown, type: string, targetX: number, targetY: number) => void
  gridSnap?: number
  bounds?: { minX: number; minY: number; maxX: number; maxY: number }
}

export function useDragAndDrop(options: UseDragAndDropOptions = {}) {
  const { onDragStart, onDragMove, onDragEnd, onDrop, gridSnap, bounds } = options

  const state = ref<DragState>({
    isDragging: false,
    draggedItem: null,
    dragType: null,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    offsetX: 0,
    offsetY: 0,
  })

  function snapToGrid(value: number, grid: number): number {
    return Math.round(value / grid) * grid
  }

  function clampToBounds(x: number, y: number): { x: number; y: number } {
    if (!bounds) return { x, y }
    return {
      x: Math.max(bounds.minX, Math.min(bounds.maxX, x)),
      y: Math.max(bounds.minY, Math.min(bounds.maxY, y)),
    }
  }

  function startDrag(
    event: MouseEvent | TouchEvent,
    item: unknown,
    type: string,
    elementOffsetX = 0,
    elementOffsetY = 0
  ) {
    const clientX = 'touches' in event ? event.touches[0].clientX : event.clientX
    const clientY = 'touches' in event ? event.touches[0].clientY : event.clientY

    state.value = {
      isDragging: true,
      draggedItem: item,
      dragType: type,
      startX: clientX,
      startY: clientY,
      currentX: clientX,
      currentY: clientY,
      offsetX: elementOffsetX,
      offsetY: elementOffsetY,
    }

    onDragStart?.(item, type)

    // Add global event listeners
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd)

    // Prevent text selection during drag
    event.preventDefault()
  }

  function handleMouseMove(event: MouseEvent) {
    if (!state.value.isDragging) return

    let x = event.clientX
    let y = event.clientY

    if (gridSnap) {
      x = snapToGrid(x, gridSnap)
      y = snapToGrid(y, gridSnap)
    }

    const clamped = clampToBounds(x, y)

    state.value.currentX = clamped.x
    state.value.currentY = clamped.y

    onDragMove?.(clamped.x, clamped.y)
  }

  function handleTouchMove(event: TouchEvent) {
    if (!state.value.isDragging) return
    event.preventDefault()

    let x = event.touches[0].clientX
    let y = event.touches[0].clientY

    if (gridSnap) {
      x = snapToGrid(x, gridSnap)
      y = snapToGrid(y, gridSnap)
    }

    const clamped = clampToBounds(x, y)

    state.value.currentX = clamped.x
    state.value.currentY = clamped.y

    onDragMove?.(clamped.x, clamped.y)
  }

  function handleMouseUp(event: MouseEvent) {
    endDrag(event.clientX, event.clientY)
  }

  function handleTouchEnd(event: TouchEvent) {
    const touch = event.changedTouches[0]
    endDrag(touch.clientX, touch.clientY)
  }

  function endDrag(clientX: number, clientY: number) {
    if (!state.value.isDragging) return

    let finalX = clientX - state.value.offsetX
    let finalY = clientY - state.value.offsetY

    if (gridSnap) {
      finalX = snapToGrid(finalX, gridSnap)
      finalY = snapToGrid(finalY, gridSnap)
    }

    const clamped = clampToBounds(finalX, finalY)

    onDragEnd?.(state.value.draggedItem, state.value.dragType!, clamped.x, clamped.y)
    onDrop?.(state.value.draggedItem, state.value.dragType!, clamped.x, clamped.y)

    // Clean up
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.removeEventListener('touchmove', handleTouchMove)
    document.removeEventListener('touchend', handleTouchEnd)

    state.value = {
      isDragging: false,
      draggedItem: null,
      dragType: null,
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
      offsetX: 0,
      offsetY: 0,
    }
  }

  function cancelDrag() {
    if (!state.value.isDragging) return

    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.removeEventListener('touchmove', handleTouchMove)
    document.removeEventListener('touchend', handleTouchEnd)

    state.value = {
      isDragging: false,
      draggedItem: null,
      dragType: null,
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
      offsetX: 0,
      offsetY: 0,
    }
  }

  // Calculate delta from start position
  function getDelta() {
    return {
      deltaX: state.value.currentX - state.value.startX,
      deltaY: state.value.currentY - state.value.startY,
    }
  }

  // Clean up on unmount
  onUnmounted(() => {
    cancelDrag()
  })

  return {
    state,
    startDrag,
    cancelDrag,
    getDelta,
  }
}

/**
 * Composable for making an element resizable
 */
export interface ResizeState {
  isResizing: boolean
  direction: string | null
  startWidth: number
  startHeight: number
  startX: number
  startY: number
}

export interface UseResizableOptions {
  minWidth?: number
  minHeight?: number
  maxWidth?: number
  maxHeight?: number
  gridSnap?: number
  onResizeStart?: () => void
  onResize?: (width: number, height: number) => void
  onResizeEnd?: (width: number, height: number) => void
}

export function useResizable(options: UseResizableOptions = {}) {
  const {
    minWidth = 50,
    minHeight = 50,
    maxWidth = Infinity,
    maxHeight = Infinity,
    gridSnap,
    onResizeStart,
    onResize,
    onResizeEnd,
  } = options

  const resizeState = ref<ResizeState>({
    isResizing: false,
    direction: null,
    startWidth: 0,
    startHeight: 0,
    startX: 0,
    startY: 0,
  })

  const currentSize = ref({ width: 0, height: 0 })

  function snapToGrid(value: number, grid: number): number {
    return Math.round(value / grid) * grid
  }

  function startResize(
    event: MouseEvent,
    direction: string,
    initialWidth: number,
    initialHeight: number
  ) {
    resizeState.value = {
      isResizing: true,
      direction,
      startWidth: initialWidth,
      startHeight: initialHeight,
      startX: event.clientX,
      startY: event.clientY,
    }

    currentSize.value = { width: initialWidth, height: initialHeight }

    onResizeStart?.()

    document.addEventListener('mousemove', handleResizeMove)
    document.addEventListener('mouseup', handleResizeEnd)

    event.preventDefault()
    event.stopPropagation()
  }

  function handleResizeMove(event: MouseEvent) {
    if (!resizeState.value.isResizing) return

    const deltaX = event.clientX - resizeState.value.startX
    const deltaY = event.clientY - resizeState.value.startY
    const direction = resizeState.value.direction

    let newWidth = resizeState.value.startWidth
    let newHeight = resizeState.value.startHeight

    if (direction?.includes('e')) {
      newWidth = resizeState.value.startWidth + deltaX
    }
    if (direction?.includes('w')) {
      newWidth = resizeState.value.startWidth - deltaX
    }
    if (direction?.includes('s')) {
      newHeight = resizeState.value.startHeight + deltaY
    }
    if (direction?.includes('n')) {
      newHeight = resizeState.value.startHeight - deltaY
    }

    // Apply grid snapping
    if (gridSnap) {
      newWidth = snapToGrid(newWidth, gridSnap)
      newHeight = snapToGrid(newHeight, gridSnap)
    }

    // Apply constraints
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth))
    newHeight = Math.max(minHeight, Math.min(maxHeight, newHeight))

    currentSize.value = { width: newWidth, height: newHeight }
    onResize?.(newWidth, newHeight)
  }

  function handleResizeEnd() {
    if (!resizeState.value.isResizing) return

    onResizeEnd?.(currentSize.value.width, currentSize.value.height)

    document.removeEventListener('mousemove', handleResizeMove)
    document.removeEventListener('mouseup', handleResizeEnd)

    resizeState.value = {
      isResizing: false,
      direction: null,
      startWidth: 0,
      startHeight: 0,
      startX: 0,
      startY: 0,
    }
  }

  onUnmounted(() => {
    document.removeEventListener('mousemove', handleResizeMove)
    document.removeEventListener('mouseup', handleResizeEnd)
  })

  return {
    resizeState,
    currentSize,
    startResize,
  }
}
