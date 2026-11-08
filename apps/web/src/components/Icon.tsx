// One consistent line icon set (Phosphor, regular weight). Names are the app's own, so call sites
// stay readable and the set can be swapped in one place.
import {
  ArrowSquareOut, ArrowsClockwise, Check, ChartBar, CaretDown, CaretRight, Copy, DotsThree, DownloadSimple, Keyboard,
  List, MagnifyingGlass, Microphone, Moon, Phone, PhoneDisconnect, Play, Pause, PushPin, Receipt, SpeakerHigh,
  SpeakerSlash, Stop, Sun, Trash, UploadSimple, Waveform, X, ForkKnife, Tag, Sliders, Record, Plus, Minus, Pepper,
  type IconProps,
} from "@phosphor-icons/react";

const ICONS = {
  phone: Phone,
  hangup: PhoneDisconnect,
  menu: ForkKnife,
  field: ChartBar,
  insights: ChartBar,
  combos: List,
  price: Tag,
  orders: Receipt,
  recordings: Waveform,
  settings: Sliders,
  sun: Sun,
  moon: Moon,
  mic: Microphone,
  keyboard: Keyboard,
  play: Play,
  pause: Pause,
  stop: Stop,
  close: X,
  copy: Copy,
  check: Check,
  retry: ArrowsClockwise,
  chevron: CaretRight,
  caret: CaretDown,
  pin: PushPin,
  speaker: SpeakerHigh,
  mute: SpeakerSlash,
  upload: UploadSimple,
  download: DownloadSimple,
  search: MagnifyingGlass,
  more: DotsThree,
  burger: List,
  trash: Trash,
  record: Record,
  open: ArrowSquareOut,
  plus: Plus,
  minus: Minus,
  chilli: Pepper,
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, size = 20, ...rest }: { name: IconName; size?: number } & Omit<IconProps, "size">) {
  const C = ICONS[name];
  return <C size={size} weight="regular" aria-hidden="true" focusable="false" style={{ flexShrink: 0 }} {...rest} />;
}
