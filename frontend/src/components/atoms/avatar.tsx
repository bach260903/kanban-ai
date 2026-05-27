export type AvatarSize = 'sm' | 'md' | 'lg'

const SIZE_CLASSES: Record<AvatarSize, string> = {
  sm: 'w-6 h-6 text-xs',
  md: 'w-8 h-8 text-sm',
  lg: 'w-10 h-10 text-base',
}

export type AvatarProps = {
  name: string
  size?: AvatarSize
  className?: string
}

export function Avatar({ name, size = 'md', className = '' }: AvatarProps) {
  const safeName = name.trim() || '?'
  const initials = safeName
    .split(' ')
    .map((w) => w[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
  const hue = safeName.charCodeAt(0) * 137 % 360

  return (
    <div
      className={`inline-flex items-center justify-center rounded-full font-medium ${SIZE_CLASSES[size]} ${className}`}
      style={{ backgroundColor: `hsl(${hue}, 60%, 50%)`, color: 'white' }}
      title={safeName}
    >
      {initials}
    </div>
  )
}
